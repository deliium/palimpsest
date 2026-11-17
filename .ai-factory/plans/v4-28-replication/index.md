<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-28 Scientific Replication

Mode: ultra
Identifier: `v4-28-replication`
Branch: `main` (existing; no branch/worktree creation)
Created: 2026-11-17
Refined: 2026-11-17 (approved `$aif-improve` pass)
Status: planned; implementation not started

## Original Request

v4-28 scientific replication

Naming requirement:

Use `v4-28-replication`.

Allow one agent/group to repeat experiments performed by others.

Track:

experiment design lineage  
conditions  
results  
measurement uncertainty  
replication relationship

Support conflicting outcomes.

Do not automatically mark a hypothesis true after N replications.

Agent communities must interpret evidence socially/cognitively.

## Settings

- Testing: yes
- Logging: verbose, metadata-only; no observation, speech, design, report, uncertainty, relationship or private ledger payloads
- Docs: yes; mandatory `$aif-docs` checkpoint at Task 27
- Language: English artifacts/UI; preserve technical terms
- Git: enabled; base `main`; create_branches false; no branch, worktree, commit or push during planning
- Workflow: slug plan ID; normal verification; explicit plan path required because this repository has multiple active plan artifacts
- Dependencies: no additional package, service or database migration planned

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations"
Rationale: Deepens V4-27's owned `science` context with owner-scoped replication and detached research evidence, without new scientific truth authority.

The user explicitly selected M8 rather than the generic first-incomplete M6. This plan does not close M8 or edit the roadmap; milestone maintenance belongs to its owner workflow.

## Requirements Reconciliation

Authority: user request defines feature scope; repository `AGENTS.md`, project axioms and architecture constrain authority/compatibility; executable current science contracts and `docs/scientific-hypotheses.md` provide the existing behavior to preserve. Roadmap entries indicate scope, not detailed behavioral overrides.

| Decision / supported requirement | Source path and section | Verification evidence |
| --- | --- | --- |
| Repeat another owner's procedure using current own/visible materials, not their private ledger | Original Request; `docs/scientific-hypotheses.md` §§Intentional tests, Communication; `src/agents/cognition/production.py::observed_experiment_operand_ids` | Tasks 4, 9, 26: source tool A, receiver tool B, ordinary Experiment admission |
| Track immutable complete design lineage and explicit source-trial → child-attempt relation | Original Request; `src/agents/cognition/scientific_hypothesis_communication.py::_claim_token` omits conditions | Tasks 1, 13–14, 17: full-payload identity and unresolved parent/source tests |
| Retain conditions, categorical results and measurement uncertainty separately | Original Request; `src/world/experimentation.py::ExperimentOutcomeClass`; `docs/scientific-hypotheses.md` §§Conditions, Confidence | Tasks 2, 4, 14, 24: conditions matched/different/unknown; declared vs unreported error |
| Conflicting reports/outcomes survive, with comparison limitations explicit | Original Request; `.ai-factory/ARCHITECTURE.md` §§Memory/testimony, Key Principles | Tasks 2–3, 14, 26: different categories, altered conditions, false testimony, missing source |
| No truth after N replications and no analytical feedback into live science | Original Request; `.ai-factory/RULES.md` §§Axioms; `docs/scientific-hypotheses.md` §§Confidence, Status | Tasks 3, 15, 26, 28: count sweeps, zero borrowed support, no true/proven field |
| Groups coordinate socially; only individual agents execute commands | Original Request; `.ai-factory/ARCHITECTURE.md` §§Objective authority, Anti-Patterns; `collective_decision_actions.COLLECTIVE_TOPIC_COMMANDS` has no Experiment | Tasks 3, 6–10, 26: participation speech vs individual execution and distinct appraisals |
| Existing science activation, no extra formal-rules gate | `docs/scientific-hypotheses.md` §Activation; `src/simulation/runner_models.py::SimulationRunnerConfig` | Tasks 12, 25: existing prerequisite/error-code matrix |
| New subjective state commits after objective finalization, never in prepare/complete | `.ai-factory/ARCHITECTURE.md` §Objective authority and runtime; `src/simulation/agent_runtime.py::finalize_pending` | Tasks 10–11: abort/crash/idempotence/fork tests |
| Existing science `complete()` mutates state precommit; narrow correction is required | `src/agents/cognition/loop.py::_remember_experiments`, `_ingest_scientific_hypotheses`, `complete`; `agent_runtime.abort_pending` | Task 10 makes science candidates detached; Task 11 persists both candidate ledgers |
| Strict old wire versions cannot acquire fields silently | `.ai-factory/ARCHITECTURE.md` §Versioned Extension Contract; `runner_serialization.decode_finalization_command`; `scientific_hypotheses_codec._TOP_KEYS` | Task 11 adds pending-finalization v2; Task 17 adds sibling snapshot v1, legacy golden bytes unchanged |
| New replication atoms must fit the actual shared world envelope | `src/world/communications.py::CommunicationRelation.__post_init__` (object cap 256) | Tasks 5, 8, 25–26: 37-character header + at most219 payload; eight real relation objects / max1,752-byte document |
| Local result/participation/appraisal state needs explicit social return paths | `phase-02-social-transport.md` — Task 7 outbox producer/destination table; `ObservedCommunication` verified speaker/listener | Tasks 3, 6–7, 10, 26: acceptance and actual result enqueue idempotent replies to verified inviter, without preloaded queues |
| Pending trial hypotheses must survive capacity pressure | `src/agents/cognition/experimentation.py::admit_hypothesis`, `apply_test_outcome` | Tasks 9–11: protected unresolved references, max-hypotheses=1 incoming-claim/delayed-result tests |
| First-use candidate construction must not mutate committed state | `src/agents/cognition/loop.py::experiment_ledger_for`, `experiment_ledger_if_present`, `run` | Tasks 10–11: nonmutating initialization, direct-run candidate carry, abort/checkpoint/finalization tests |
| Identity and layer mappings are explicit before publication | `phase-04-detached-analysis.md` — exact fact/row/identity tables; `phase-05-publication-and-store.md` — exact collection mapping | Tasks 1, 13–18: non-self-referential hash, one-time token mapping, execution/report tagged union, intact cross-table references |
| Existing published science snapshots cannot prove per-trial replication | `src/experiments/scientific_hypotheses_publication.py`; `src/analysis/scientific_hypotheses_analysis.py` | Tasks 13, 16–17 retain raw qualified trial associations before aggregation, full-content hashes |
| Preserve default-off behavior and unowned capabilities | `.ai-factory/ARCHITECTURE.md` §§Capability ownership, Current baseline through V4-27 | Tasks 12, 28: science-off parity, first250 catalog prefix, closed-world pins |

### Supported combinations and transitions

| Accepted input/state | Retained state → output/transition | Invariants / verification |
| --- | --- | --- |
| Science off; any replication-like speech | No replication sidecar/candidate; old behavior/bytes | No new messages, finalization v1; Task 12 |
| Science on without existing prerequisites | Existing config rejection | No new flag/schema/prerequisite interpretation; Task 12 |
| Science on, original local test, actor-visible result | Pre-action draft → frozen source design + own result report | No original test mislabeled replication; Tasks 1, 10 |
| Complete delivered design + testable invitation; trusted/unknown source | Receiver receipt/participation intent → independently selected ordinary Experiment if default Wait | Unknown testimony may motivate inquiry, not confidence; Tasks 6, 9 |
| Complete delivered design without invitation | Stored testimony only; no automatic test | Explicit owner-local request may still initiate inquiry; Tasks 7, 9 |
| Contested source | Retained contested report/appraisal; no automatic recruitment | Explicit owner-local request may challenge it; Tasks 3, 9 |
| Same-kind selector and receiver's observed equivalent material | New concrete binding, same frozen procedure; `repeat` relation | No source-owned item access; Tasks 4, 26 |
| Exact selector unavailable or requested condition missing/different | Skip/retain request; no fabricated result | Missing is not failure; Tasks 4, 9 |
| Deliberately changed condition/selector | New parent-linked design; `adapted` relation | Never silently equivalent/exact; Tasks 1, 4, 14 |
| Proposed Experiment replaced before submission | No submitted replication attempt; discard corresponding candidate test formulation | Final effective command governs; Task 10 |
| Hypothesis cap reached while old test is unresolved | Protect old hypothesis; reject conflicting new admission without an orphan attempt | Incoming `hyp_v1` and ordinary science admissions use same temporary protection; Tasks 9–11 |
| Submitted Experiment rejected | Rejected attempt, no measurement | Rejection is not contradictory scientific data; Task 10 |
| Actor-visible unambiguous result | Own measurement + exactly-once local scientific evidence | Match source tick/operator/target; no private event input; Task 10 |
| Missing/ambiguous result or witness-only occurrence | Unresolved state; no own experimental support | Explicit missingness and limited correlation; Task 10 |
| Communicated result or duplicate source report | Owner testimony/interpretation, source deduplication | No borrowed evidence IDs/mass or independent-trial count; Tasks 2, 6, 14 |
| Existing `learn_into_genealogy` off/on | Preserve that independent opt-in bounded-experimentation policy for the owner's direct tests | Replication/testimony counts add no new uplift rule and never establish truth; Tasks 9–12 |
| Different known categories under matched conditions | Both reports retained; categorical conflict, uncertainty caveat retained | No truth winner; Tasks 3, 14, 26 |
| Different categories with different/unknown conditions | Category difference retained; not-comparable/inconclusive qualification | Excluded from exact comparison denominator; Tasks 14–15 |
| Missing uncertainty vs declared categorical alternative set | `unreported` vs `declared_set` with explicit possible outcomes | No zero error, numeric CI or alias to hypothesis confidence; Tasks 2, 24 |
| Group invitation/acknowledgements without performed tests | Attributed intentions only | No group actor, roster proof or execution result; Tasks 3, 8 |
| Abort / commit / repeated finalize / pending recovery | Discard candidates / commit once / no-op / reconstruct exact v2 candidates | No rerun cognition or state leakage; Tasks 10–11 |
| First-use direct `CognitiveLoop.run()` without runtime coordinator | Returns detached science/replication candidates; committed state remains absent | Continuing standalone caller explicitly carries accepted state; Task 10 |
| Legacy pending v1 / new science pending v2 | Exact v1 decode absent new state / strict two-state v2 | Legacy bytes preserved; malformed present state rejected; Task 11 |
| Capacity exhausted, missing export, absent publication | Explicit partial/unavailable evidence; historical data retained | Never fabricated known-zero/complete; Tasks 14, 18–19 |
| New publication while paging old publication | Old signed cursor keeps old snapshot; fresh query sees latest | All filters/content bound; Tasks 20–24 |

### Source discrepancies and resolved scope

- DESCRIPTION and older ARCHITECTURE/ROADMAP paragraphs retain historical or contradictory “current” counts. The latest V4-27 sections and executable registry tests agree on 250 families/17 contexts/12 flags/nine owned before this feature. Task 15 validates the prefix, appends six and migrates current catalog pins; Task 28 reruns final qualification. Do not globally replace historical numbers.
- The context registry's prose lists a formal-rules prerequisite for science, but executable activation and current science documentation do not require `formal_rules=True`. Preserve current executable activation; this plan does not add that requirement.
- Existing direct science precommit mutation conflicts with the documented finalization boundary. Correct only the science-enabled path needed for replication; do not adopt the bug as the new contract.
- No research artifact is present or used. There is no Research Context copy or external research dependency.
- No blocking product question remains. Numeric metrology, general multi-hop testimony, cross-run live imports and guaranteed autonomous recruitment are explicitly outside this implementation scope.

## Architecture and Decisions

1. **Owned seam:** deepen `science` on existing accepted `runner-config-v56`; prerequisites unchanged. No new V4 context/flag/mode, runner root field or v57.
2. **Owner state:** new frozen `ReplicationLedger`; existing `ExperimentLedger` shape stays intact. Its science-enabled candidate lifecycle becomes transactional. No shared scientific state.
   Read-only access/first-use local construction replace the lazy-mutating accessor on this path. Direct `run()` returns candidates; only runtime finalization installs them. Temporarily protect hypotheses referenced by pending tests/drafts against eviction.
3. **Frozen procedure:** full-content design identity covers operator/process/selectors/prediction/conditions/parent/source, using the exact preimage excluding `design_token` itself. Same-kind selectors let a receiver use equivalent own materials; current observations and ordinary engine admission remain authoritative.
4. **Source capture:** retain pre-action safe descriptors for original tests, then freeze only after actor-visible result. Unavailable data stays unavailable; consumed operands never require hidden-state reconstruction.
5. **Replication vs lineage:** design parent edges and source-trial → attempted repeat edges are different records. Missing source, distinct reported source and objectively distinct execution are separately qualified.
6. **Uncertainty:** current physics exposes five categorical outcomes. Record measurement resolution, explicitly unreported uncertainty or a declared alternative set; do not fabricate numeric intervals, sensor precision, confidence probabilities or independence.
7. **Social cognition:** actual Talk/Tell delivery carries complete `rep_v1` documents as at most eight 256-character world atoms (37-character header,219-character payload; max1,752 document bytes). Individual directed trust changes local appraisal and recruitment. Source offers are generated only for an already-selected speech recipient; dependency-ready queues send designs first, retain public sender echoes and stop after three unobserved delivery attempts. Acceptance, completed tests and appraisal revisions explicitly enqueue replies to the verified inviter; no recipient is invented. Automatic execution requires delivered invitation plus complete design; design alone is testimony. Repeated testimony never becomes independent evidence. Groups are attributed collaboration claims and individual trials, not actors.
8. **Action policy:** decorate existing Talk/Tell; replace only default Wait with one ordinary Experiment. One attempt per accepted invitation; explicit later requests permit further trials. Meaningful commands, caps and engine validation survive.
9. **Transactional recovery:** new `finalization-command-v2` only for science/replication transitions, plus strict nested subjective state codecs including recipient-specific outbox state. Keep v1 default bytes. Pending recovery is not complete durable subjective resume. Correlated attempts/source drafts drive both measurements and exact local hypothesis scoring; never let the legacy newest-operator/operand fallback credit another condition variant.
10. **Research authority:** exact neutral fact/row schemas → six append-only metric families → sibling `scientific-replication-snapshot-v1` / store v1. The bridge tokenizes each identity once and reuses the reference map throughout. `results` is an explicit execution/report tagged union: objective receipts and subjective claims remain separate, with reported/execution comparison bases distinguished. New research data never feeds cognition, world, prompts, memory, stop selectors or observer semantics.
11. **Read surfaces:** eight dual-gated GET routes and a read-only Research UI panel, full pagination pinned to immutable publication. Programmatic publication only; API configuration attaches readers, not capture/science.
12. **Current pins after completion:** 256 metric families (first250 unchanged), 17 V4 contexts, 12 flags, nine owned/three unowned, 43 commands, 73 observer semantics, latest feature-selected replay-v27/codec v25, Alembic0017, `/v1`, `observer-protocol-v1`; default runner/result v4/v2, existing v55/v56 feature families. New pending v2 is not a world codec.

### Non-goals

No objective hypothesis truth, N-count promotion, majority consensus, universal scientific score, OrganizationLLM/group executor, global experiment registry, new automatic knowledge inheritance/uplift from replication counts, new physical experiment law mechanics, calibrated numeric error bars, general multi-hop tracking, SQL migration, Godot overlay, `/v2`, new package/service, or civilization throughput claim. Existing independently gated direct-test learning remains separate from truth. Preserve contradictions rather than force convergence.

## Phase Index

1. [Phase 1: Owner-scoped replication contracts](phase-01-owner-contracts.md) — Tasks 1–4
2. [Phase 2: Bounded social transport](phase-02-social-transport.md) — Tasks 5–8
3. [Phase 3: Ordinary execution, transactional state, and recovery](phase-03-runtime-and-recovery.md) — Tasks 9–12
4. [Phase 4: Detached lineage, comparisons, and metrics](phase-04-detached-analysis.md) — Tasks 13–16
5. [Phase 5: Immutable publication and bounded reads](phase-05-publication-and-store.md) — Tasks 17–20
6. [Phase 6: Read-only API and Research UI](phase-06-api-and-research-ui.md) — Tasks 21–24
7. [Phase 7: Scientific scenarios, regression gates, and documentation](phase-07-experiments-and-gates.md) — Tasks 25–28

## Cross-Phase Dependencies

- Tasks 1–4 establish models, provenance, interpretation and binding contracts.
- Task 5 depends on 1–4; Task 6 on 3,5; Task 7 on 5–6; Task 8 on 5–7.
- Task 9 depends on 1–8; Task 10 on 9; Task 11 on 10; Task 12 on 10–11.
- Task 13 depends on 1–4,11–12; Task 14 on 13; Task 15 on 14; Task 16 on 12–15.
- Task 17 depends on 13–16; Task 18 on 17; Task 19 on 17–18; Task 20 on 17–19.
- Task 21 depends on 18–20; Task 22 on 21; Task 23 on 21; Task 24 on 22–23.
- Task 25 depends on 12,15–16; Task 26 on 19,22,24–25; Task 27 on 1–26; Task 28 on 1–27.
- Task 15 owns catalog registration **and current pin migration**, including the old science-family slice `[244:250]`; Task 27's pin verification consumes that completed prerequisite. Task 28 verifies the migration, not introduces it.
- Execute the phase order above sequentially; dependencies allow review isolation, not parallel owner-state mutation.

## Tasks

### Phase 1: Owner contracts

- [x] Task 1: Define frozen design identity and lineage ([details](phase-01-owner-contracts.md#task-1-define-frozen-design-identity-and-lineage))
- [x] Task 2: Model attempts, measurements, and conflicting result reports ([details](phase-01-owner-contracts.md#task-2-model-attempts-measurements-and-conflicting-result-reports)) (depends on 1)
- [x] Task 3: Define collaboration and owner-relative evidence interpretation ([details](phase-01-owner-contracts.md#task-3-define-collaboration-and-owner-relative-evidence-interpretation)) (depends on 1,2)
- [x] Task 4: Implement observation-only operand binding and comparison ([details](phase-01-owner-contracts.md#task-4-implement-observation-only-operand-binding-and-comparison)) (depends on 1,2)

### Phase 2: Social transport

- [x] Task 5: Specify and encode the `rep_v1` protocol ([details](phase-02-social-transport.md#task-5-specify-and-encode-the-rep_v1-protocol)) (depends on 1–4)
- [x] Task 6: Ingest delivered designs and reports without borrowed evidence ([details](phase-02-social-transport.md#task-6-ingest-delivered-designs-and-reports-without-borrowed-evidence)) (depends on 3,5)
- [x] Task 7: Select replication speech and preserve existing commands ([details](phase-02-social-transport.md#task-7-select-replication-speech-and-preserve-existing-commands)) (depends on 5,6)
- [x] Task 8: Prove social interpretation and transport boundaries ([details](phase-02-social-transport.md#task-8-prove-social-interpretation-and-transport-boundaries)) (depends on 5–7)

### Phase 3: Runtime and recovery

- [x] Task 9: Compile one receiver-owned ordinary experiment ([details](phase-03-runtime-and-recovery.md#task-9-compile-one-receiver-owned-ordinary-experiment)) (depends on 1–8)
- [x] Task 10: Stage and finalize science/replication updates transactionally ([details](phase-03-runtime-and-recovery.md#task-10-stage-and-finalize-sciencereplication-updates-transactionally)) (depends on 9)
- [x] Task 11: Version pending payloads and preserve fork/checkpoint state ([details](phase-03-runtime-and-recovery.md#task-11-version-pending-payloads-and-preserve-forkcheckpoint-state)) (depends on 10)
- [x] Task 12: Lock activation, owner boundaries, and off-path compatibility ([details](phase-03-runtime-and-recovery.md#task-12-lock-activation-owner-boundaries-and-off-path-compatibility)) (depends on 10,11)

### Phase 4: Detached analysis

- [x] Task 13: Define detached facts, scoped identities, and layer guards ([details](phase-04-detached-analysis.md#task-13-define-detached-facts-scoped-identities-and-layer-guards)) (depends on 1–4,11,12)
- [x] Task 14: Reconstruct replication edges and qualified outcome comparisons ([details](phase-04-detached-analysis.md#task-14-reconstruct-replication-edges-and-qualified-outcome-comparisons)) (depends on 13)
- [x] Task 15: Append six descriptive replication metric families ([details](phase-04-detached-analysis.md#task-15-append-six-descriptive-replication-metric-families)) (depends on 14)
- [x] Task 16: Compose completed-run facts and collector inputs ([details](phase-04-detached-analysis.md#task-16-compose-completed-run-facts-and-collector-inputs)) (depends on 12–15)

### Phase 5: Publication and store

- [x] Task 17: Define and encode the replication snapshot ([details](phase-05-publication-and-store.md#task-17-define-and-encode-the-replication-snapshot)) (depends on 13–16)
- [x] Task 18: Add publication/read ports and trusted composition ([details](phase-05-publication-and-store.md#task-18-add-publicationread-ports-and-trusted-composition)) (depends on 17)
- [x] Task 19: Implement atomic quota-bounded filesystem storage ([details](phase-05-publication-and-store.md#task-19-implement-atomic-quota-bounded-filesystem-storage)) (depends on 17,18)
- [x] Task 20: Define stable keyset paging and query identity ([details](phase-05-publication-and-store.md#task-20-define-stable-keyset-paging-and-query-identity)) (depends on 17–19)

### Phase 6: API and Research UI

- [x] Task 21: Add dual-gated snapshot-pinned GET routes ([details](phase-06-api-and-research-ui.md#task-21-add-dual-gated-snapshot-pinned-get-routes)) (depends on 18–20)
- [x] Task 22: Prove API paging, publication pinning and safe failure ([details](phase-06-api-and-research-ui.md#task-22-prove-api-paging-publication-pinning-and-safe-failure)) (depends on 21)
- [x] Task 23: Add typed Research UI API and pagination state ([details](phase-06-api-and-research-ui.md#task-23-add-typed-research-ui-api-and-pagination-state)) (depends on 21)
- [x] Task 24: Render evidence-scoped replication and community disagreement ([details](phase-06-api-and-research-ui.md#task-24-render-evidence-scoped-replication-and-community-disagreement)) (depends on 22,23)

### Phase 7: Experiments and completion gates

- [x] Task 25: Register a bounded scientific replication experiment ([details](phase-07-experiments-and-gates.md#task-25-register-a-bounded-scientific-replication-experiment)) (depends on 12,15,16)
- [x] Task 26: Exercise real source → receiver → community → publication paths ([details](phase-07-experiments-and-gates.md#task-26-exercise-real-source--receiver--community--publication-paths)) (depends on 19,22,24,25)
- [x] Task 27: Complete the mandatory documentation checkpoint ([details](phase-07-experiments-and-gates.md#task-27-complete-the-mandatory-documentation-checkpoint)) (depends on 1–26)
- [x] Task 28: Lock pins and run implementation completion gates ([details](phase-07-experiments-and-gates.md#task-28-lock-pins-and-run-implementation-completion-gates)) (depends on 1–27)

## Commit Plan

Suggested implementation checkpoints only; this plan command does not commit.

1. After Tasks 1–4: `feat(science): define owner-scoped replication designs and evidence`
2. After Tasks 5–8: `feat(science): exchange bounded replication testimony and participation`
3. After Tasks 9–12: `feat(science): finalize and recover individual replication trials`
4. After Tasks 13–16: `feat(analysis): add qualified scientific replication metrics`
5. After Tasks 17–20: `feat(persistence): publish immutable scientific replication evidence`
6. After Tasks 21–24: `feat(research): inspect replication lineage and conflicting evidence`
7. After Tasks 25–28: `feat(science): qualify replication scenarios and compatibility gates`

## Definition of Done

- A real source agent performs an experiment; another receives a complete immutable design and independently repeats it using ordinary commands/materials.
- Real 256-character communication atoms carry the source design and return the receiver's result to the verified inviter through an ordinary speech opportunity; the test does not preload reply queues.
- Community participation is attributed speech plus individual execution; differing owner interpretations survive.
- Design lineage, conditions, results, measurement uncertainty and explicit replication relationship survive runtime, completed-run analysis, snapshot/store, routes and UI.
- Conflicting categories/reports and missing/changed conditions remain visible; no N-count, vote or analytical output establishes truth.
- Trial occurrence, testimony multiplicity and statistical independence remain distinct concepts.
- New science/replication candidates commit only after objective finalization, abort safely, recover through strict pending v2, and survive process-local forks/retirement without newborn copying.
- First-use/direct-run candidate construction remains nonmutating; delayed results retain their protected hypothesis at capacity and every published reference survives one-time mapping.
- Legacy science-off/default bytes, pending v1, scientific snapshot v1, result wire schemas and first250 metric family contracts remain unchanged.
- All task-specific verification and mandatory local gates pass with coverage; unavailable operational prerequisites are not reported as passed.
- Mandatory documentation checkpoint completes; no unsupported emergence, full subjective restart, numeric metrology or scale certification is claimed.

## Approved Refinements

2026-11-17 — `$aif-improve`, all six findings approved; 28 task IDs/progress states retained:

1. Corrected multipart transport to the actual shared 256-character object limit, with eight parts/max1,752 bytes and real relation/delivery tests.
2. Defined verified inviter routing and idempotent producers for participation, decline, observed results and revised interpretations.
3. Closed lazy first-use mutation; defined direct-run candidate carry and reused the existing validated installation primitive.
4. Protected pending hypothesis references under configured caps and included admission-pressure/recovery regressions.
5. Fixed design hash preimages, exact neutral/public row schemas, single-pass token mapping, and execution/report publication and UI separation.
6. Moved current catalog pin migration alongside Task 15 registration so Task 27's verification no longer depends on future Task 28 work.

No implementation was started, no task was marked complete, and the Original Request/settings/milestone remain unchanged.

## Implementation Handoff

Read this index and the complete linked phase file before each task; update checkboxes here only after verification. Begin with Task 1, not a new architecture exploration. Resolve later material deviations by refining this bundle rather than silently changing scope.

Start explicitly with `$aif-implement .ai-factory/plans/v4-28-replication/index.md`.
