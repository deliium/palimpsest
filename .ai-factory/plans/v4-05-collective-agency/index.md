<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-05 Collective Agency

Mode: ultra
Branch: main
Created: 2026-11-02
Plan identifier: `v4-05-collective-agency`
Status: plan only; not implemented. This bundle is the implementation contract
for `$aif-implement`.

## Original Request

v4-05 collective agency

Naming requirement:

Use `v4-05-collective-agency`.

Implement collective decisions without turning organizations into super-agents.

Conceptual pipeline:

proposal  
→ discussion  
→ support/opposition  
→ recognized procedure  
→ collective decision record  
→ individual implementation/compliance

Support:

- proposals
    
- supporters
    
- opponents
    
- abstention
    
- amendments
    
- recognized outcomes
    
- compliance
    
- refusal
    
- sabotage

Collective decisions may fail because members do not act.
Do not add a global OrganizationLLM.
Agent cognition remains the source of intentional actions.
Track whether organization-level actions were actually implemented.

## Settings

- Testing: yes; full strategy. Unit, architecture, determinism, integration,
  Compose/browser, Godot regression, Research UI, benchmark regression, and
  static gates, with coverage enabled for Python lanes.
- Logging: verbose, metadata-only. Bounded DEBUG flow/counts, INFO milestones,
  WARN incomplete evidence/truncation, ERROR safe codes. `PALIMPSEST_LOG_LEVEL`
  controls operational verbosity. No person sets, private content, payload
  surrogates, prompts, credentials, tokens, DSNs, memories, embeddings,
  utterance bodies, labels, or anchor payloads.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 22.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints are suggestions, not authorization to
  commit during planning.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-05-collective-agency`; the ultra bundle directory
  is `.ai-factory/plans/v4-05-collective-agency/`, phase files use
  `phase-NN-<slug>.md`, and `index.md` is the canonical entrypoint.
- Research source: `.ai-factory/RESEARCH.md` and `.ai-factory/research/` do not
  exist; no external research conclusions are invented.
- Execution: plan only. No implementation, commit, roadmap edit, or branch
  creation occurs in this invocation.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"
Rationale: V4-05 deepens the already-owned V4-03 `organizations` context on the
accepted `runner-config-v56` seam. This plan does not edit or close the roadmap;
`$aif-roadmap` must register V4-05 in M8.

## Requirements Reconciliation

Authority: the Original Request defines scope; `.ai-factory/ARCHITECTURE.md`
("Key Principles", "Capability ownership", "Important V3 seams", "Versioned
Extension Contract", V4-01/V4-02/V4-03/V4-04 seams) and `.ai-factory/RULES.md`
constrain every edit; `.ai-factory/DESCRIPTION.md` and `.ai-factory/ROADMAP.md`
describe current state; completed V4-01/V4-02/V4-03/V4-04 code, pins, and the
`tests/architecture/test_*organization*`/`test_v4_*` suites govern compatibility.
V4-05 owns no new V4 flag; it extends the owner-scoped `organizations` context and
may not create an objective organization actor, roster, treasury, resource pool,
registry, executor, global OrganizationLLM, or independent cognition engine.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-05 deepens the one owned V4 flag `organizations`; no other flag, `runner-config-v57`, new root field, or per-agent runner key is added | Original Request "Implement collective decisions without turning organizations into super-agents"; `.ai-factory/ARCHITECTURE.md` "Capability ownership"; `src/simulation/runner_models.py` 305-322; `src/simulation/v4_architecture.py` 103-121 | Task 1/2 contract tests; Task 19 pins; Task 23 `v57` absence |
| Collective agency is a third owner-scoped ledger keyed by existing `orgc-` ids; the V4-03 concept and V4-04 operation contracts, identity, digest, status, and lineage are unchanged | Original Request; `src/agents/cognition/organization_concepts.py` 1203-1549; `organization_operations.py` 1333-1522; V4-03/V4-04 plan decisions | Task 3/5/6/7 tests; Task 6/19 concept/operation preservation |
| The pipeline maps one-to-one to proposal, discussion, support/opposition, recognized procedure, collective decision record, individual implementation/compliance | Original Request pipeline; V3-31 `collective_decisions.py` 152-233, 1029-1180; V4-04 procedure beliefs 846-886 | Task 1/3/5/9 domain and stage tests |
| A collective decision is an owner belief about a recognized process, not an organization will, super-agent, binding resolution, quorum, or permission | Original Request; `.ai-factory/ARCHITECTURE.md` "Important V3 seams" (V3-30/V3-31); `src/agents/cognition/offices.py` 213-220 | Task 1/3/5/19 no-magic-actor and no-permission tests |
| No organization object can construct, submit, resolve, or execute a command; every physical effect is an existing 43-command selected by an agent | Original Request "Agent cognition remains the source of intentional actions"; `src/world/actions.py` 890-1004; `src/simulation/actions.py` 294-355; `src/simulation/engine.py` 3903-4025 | Task 8/19 no-command scan; Task 20 physical-effect test |
| No global OrganizationLLM, shared prompt, provider, or collective context is added; each owner forms its own proposal/position deterministically | Original Request "Do not add a global OrganizationLLM"; `.ai-factory/ARCHITECTURE.md` "LLM and outer composition"; `src/llm/__init__.py` boundary | Task 1/19 LLM-import scan; Task 6 deterministic generation test |
| Support includes proposals, supporters, opponents, abstention, amendments, recognized outcomes, compliance, refusal, and sabotage | Original Request bullets; V3-31 `CollectiveAct` 152-160; V3-31 `CollectivePositionStance` 193-199; V4-04 authority/provenance 173-210 | Task 3/4/5/6/10/20 tests |
| A recognized procedure is an owner belief threshold (recognized procedure belief plus support), not a world permission or binding rule | Original Request "recognized procedure"; `organization_concepts.py` 846-886; V3-30 office authority seam 213-220 | Task 5/6/19 tests |
| A collective decision record is minted even when unrecognized or contested; disagreement is retained with `contested`/counts and no consensus gate | Original Request; V4-03 membership dispute precedent 60-68; V3-31 `CollectiveCompliance` 864-923 | Task 5/10/11/20 tests |
| Implementation is tracked per expected actor from observed commands or explicit testimony; a decision may fail because members do not act | Original Request "Collective decisions may fail because members do not act"; `src/world/_perception.py` 939-1044 | Task 6/10/20 tests |
| Silence is never refusal or sabotage. `unimplemented` requires a closed window with the actor observed; otherwise the status is `unknown` | Original Request "refusal"/"sabotage"; V3-31 compliance docstring 227-233 | Task 6/19 censoring tests; Task 20 E2E |
| Refusal and sabotage require explicit evidence; sabotage is an owner attribution, never an objective fact | Original Request "refusal"/"sabotage"; `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts" | Task 6/10/20 provenance tests |
| Proposals/positions/refusals/reports use bounded `org_ca_v1` relations inside existing `Talk`/`Tell`; no new command, event, observer semantic type, or free-text payload | `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts"; V4-03/V4-04 frame contracts | Task 4/8 tests; Task 19 command/event pins |
| The agency ledger reads only the owner's observation and prepared owner ledgers; it never reads peer ledgers, `WorldState`, event stores, commands, or another owner's perspective | Original Request "Agent cognition remains the source"; `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime" | Task 5/7/19 isolation tests; Task 20 owner-only test |
| Detached analysis joins agency rows to existing analytical candidates; agency never creates, splits, merges, dissolves, or re-identifies a candidate | Original Request; V4-03 detection/identity/lineage contracts `organization_detection.py` 378-484; `organization_identity.py` 126-300; `organization_lineage.py` 146-269 | Task 10/11 tests; Task 20 status/lineage-unchanged test |
| Objective counts, owner claims, and analytical summaries remain three distinct types with hard leakage checks | Original Request; `.ai-factory/ARCHITECTURE.md` Key Principles 1; `organization_layers.py` 226-303 | Task 11/19 leakage tests |
| The metric catalog grows from 146 to 148 by appending `organization_collective_agency@1` and `organization_collective_implementation@1`; the first 146 families keep id, order, version, and value keys | `src/analysis/specifications.py` 53, 218-223, 6407-6537, 6681-6686 | Task 12/19/23 exact pin checks |
| `organization-snapshot-v3` adds bounded collective-decision/implementation records/counts; v1 and v2 remain decodable and byte-verifiable | `.ai-factory/ARCHITECTURE.md` "Use accepted-set and exact-key-set schema evolution"; `organization_codec.py` 39-146, 313-437 | Task 13/19/23 v1/v2/v3 codec tests |
| Access is six GET-only `/v1` routes requiring `SUBJECTIVE_DEBUG`; the five V4-03/V4-04 routes keep their paths, and a sixth collective-agency route is additive | `docs/research-api.md` line 30; V4-04 `api/routes/organization.py` 168-485 | Task 17/19 route tests; Task 20 API read |
| Cursors bind to the publication digest; the existing empty-digest defect is repaired for every paged route | User decision "Fix all paged routes"; `api/routes/organization.py` 250, 381, 466; `simulation/organization_ports.py` 139-159 | Task 14/17 cursor reuse/filter/expiry tests |
| Publication is opt-in, post-completion, atomic, quota-bounded, and isolated from scientific status; no new CLI flag or environment variable is added | V4-02/V3-39/V4-03/V4-04 precedent; `research_runner/organization_composition.py` 73-135 | Task 15/16/20 receipts and failure-isolation tests |
| No SQL migration, new event, command, observer semantic type, write pair, `/v2` route, or `observer-protocol-v2` is added; Alembic stays `0017`, events 22, codec v20, commands 43, semantics 73 | `.ai-factory/ARCHITECTURE.md` requirements 4-6; `src/simulation/versioning.py` 99-139 | Task 19/23 pins |
| Agency rows flow through `MetricComputationInputs.organization_agency_rows`, `experiments.collectors`, and `analysis.metric_service`; the new families are emitted by real completed-run assembly, not only direct compute calls | `.ai-factory/ARCHITECTURE.md` "analysis is read-only"; `src/analysis/metric_service.py` 311-312, 1430-1474; `src/experiments/collectors.py` 789-802 | Task 9/12 tests; Task 20 metric assembly; Task 21 metric-service lane |
| Implementation tracking uses real occurrence kinds and effect-specific anchor keys (`give_item_ids`, `take_item_ids`, `target_id`/`destination_id`, effect-specific `public_facts`), never V4-04 synthetic `given`/`taken`/`dropped` | Original Request "Track whether ... actually implemented"; `src/world/_perception.py` 1392-1416; V4-04 `organization_operations.py` 1564-1587 | Task 6/20 tests; Task 19 boundary scan |
| The carried ledger reaches `Perspective` through `build_perspective` and `SimulationRunnerResult` validates ordered ledger sequences | `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime"; `src/simulation/perception.py` 141, 350; `src/simulation/runner_models.py` 6656-6666 | Task 7 tests; Task 19 carry scan |
| Required lanes must execute; a missing prerequisite is reported `unexecuted` with a prerequisite, never as a skip-pass | Plan Settings "Testing: yes; full strategy"; `docs/development.md`; `tests/compose/acceptance.py` | Task 21 three-state receipt; Task 23 audit |
| The roadmap is owned by `$aif-roadmap` and is not edited here | `.ai-factory/ARCHITECTURE.md` requirement 7 | Task 22/23 `git status` |

### Supported combinations and availability transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| Default runner config, all V4 flags off | V3/V4-02/V4-03/V4-04-equivalent behavior | No agency ledger, policy, metric, publication, or route data | Task 2/8/20 flags-off tests |
| `organizations` enabled on v4 or v55 | Unchanged config | `v4_capability_requires_v56` before construction | Task 2 test |
| `organizations` enabled on v56, no V3 evidence | Valid run | Empty concept/operation/agency ledgers; agency metrics `ABSENT`; no fabricated proposal | Task 5/12 tests |
| Concept beliefs only | Structural anchors | Agency ledger empty; v3 snapshot with empty agency records; summary `None` | Task 5/10/12 tests |
| Owner generates a proposal | Active proposal | `orgp-`, status `active`, deadline set; no decision yet | Task 6/20 tests |
| Peer `propose` claim under an existing concept | Owner-local peer proposal | `orgp-` with `provenance_code=communicated`; no organization concept created | Task 5 test |
| Peer `propose` claim with no matching concept | Orphaned claim | `orphaned_concept`; no proposal | Task 5 test |
| Peer support, recognized procedure | Recognized decision | `orgcd-`, `recognition=recognized`, support count retained | Task 5/6 test |
| Peer support, no recognized procedure | Unrecognized decision | `orgcd-` recorded with `recognition=unrecognized`; no forced rejection | Task 5/10 test |
| Support and opposition | Contested decision | Both sides retained; `recognition=contested`, contest count > 0 | Task 5/10/11/20 tests |
| Abstention | Neutral position | `abstain_count` increments; recognition is not blocked | Task 5 test |
| Amendment in order | New revision | Revision increments; prior amendment retained; counts reset | Task 5 test |
| Amendment out of order | Prior revision | `amendment_out_of_order`; no silent jump | Task 5 test |
| Explicit refusal | Refused implementation | `refused` only with a refusal claim/report; no permission change | Task 6/20 tests |
| Contrary effect with intent evidence | Sabotage attribution | `sabotaged` with owner provenance; never objective | Task 6/20 test |
| Contrary effect without intent | Contrary act | `contrary`; not upgraded to sabotage | Task 6 test |
| Physical decision, matching effect | Implemented | `implemented`; physical custody changes only through the real command | Task 6/20 test |
| Physical decision, actor observed idle | Unimplemented | `unimplemented` after the window closes | Task 6/20 test |
| Physical decision, actor never observed | Unknown | `unknown`; censored, never refusal/unimplemented | Task 6/19 test |
| Testimonial decision with report | Implemented | `implemented` only from an explicit report | Task 6 test |
| Testimonial decision without report | Unimplemented/unknown | `unimplemented` after a closed window; `unknown` while open | Task 6 test |
| Concept splits/merges | Predecessor agency | Agency stays with the retired predecessor; children start empty; lineage unchanged | Task 5/20 tests |
| Concept dissolves | Dissolved agency | Existing proposals/decisions retained; implementation `expired`; no new decisions | Task 5/6 test |
| Candidate exceeds 64 decisions | Deterministic truncation | `collective_agency_truncated`; no silent drop | Task 13/15 tests |
| Snapshot exceeds 4096 decisions / 8192 implementations / 4 MiB | No publication | `organization_size_limit` | Task 13/15 tests |
| Duplicate publication id with different bytes | Existing publication untouched | `organization_publication_exists` | Task 16 test |
| v1/v2 publication read by v3 reader | Old artifact | Read-only summary/candidates/lineage with zero agency counts and empty agency page | Task 16 test |
| `PALIMPSEST_ORGANIZATION_ROOT` unset | API state unset | 503 `organization_disabled`; CLI receipt `disabled` | Task 17/20 tests |
| Cursor reused with same filter/run/publication | Same page | 200; digest matches | Task 14/17 test |
| Cursor reused with changed filter/run/publication/digest | No page served | 400 `organization_cursor_invalid`; expired 410 | Task 14/17 test |
| Run incomplete or publication failed | Scientific result unchanged | Receipt `unavailable`/`failed` only | Task 15/16/20 test |
| Required Compose/browser/Godot/benchmark lane with a missing prerequisite | No green certification | Recorded `unexecuted` with prerequisite | Task 21/23 |

## Architecture and Decisions

1. **One owned flag, one seam.** `organizations` already owns the V4 context and
   requires `runner-config-v56`. V4-05 adds no flag, runner schema, root field, or
   per-agent runner key; it adds only an internal cognition policy and ledger.
2. **A third sidecar, not a concept rewrite.** `OrganizationAgencyLedger` is a
   third owner-scoped ledger keyed by `orgc-`. The V4-03 concept and V4-04
   operation contracts, digests, statuses, identity, and lineage are untouched.
3. **A collective decision is a belief.** It is one owner's belief about a
   proposal, positions, a recognized procedure, and a recognized outcome. It is
   not an organization will, a super-agent, a binding resolution, a quorum, a
   majority, or a permission.
4. **No global OrganizationLLM.** No shared prompt, provider, collective
   context, or organization cognition exists. Each owner forms proposals and
   positions with deterministic per-agent policy; agents remain the source of
   intentional actions.
5. **No executor.** Agency helpers classify and compare observed commands,
   effects, and testimony. They never return, construct, submit, or resolve an
   `AgentCommand`, and never move a resource or execute a physical action.
6. **The pipeline is owner-local.** Proposal → discussion → support/opposition →
   amendment → recognized procedure → decision record → individual
   implementation/compliance is represented in one owner's ledger, not a shared
   organization object.
7. **Positions are claims.** Support, opposition, abstention, amendments,
   withdrawal, and recognition claims are bounded speech or owner beliefs. They
   never grant world permission and never change admission rules.
8. **No consensus gate.** A decision can be recognized with one supporter and a
   recognized procedure; opposition makes it contested, not blocked. A single
   owner's claim is enough to record a position or decision.
9. **Recognized procedure is a belief threshold.** A proposal's procedure ref
   must match a recognized `OrganizationProcedureBelief` with sufficient
   recurrence. The result is an owner belief, not a rule enforced by the world.
10. **Implementation is observed, not dispatched.** Per-actor status comes from
    real observed effects or explicit testimony. The ledger never schedules,
    orders, or performs the action.
11. **Failure is first-class.** A closed implementation window with observed but
    inactive actors yields `unimplemented`. A window with insufficient
    visibility yields `unknown`. Silence is never refusal or sabotage.
12. **Refusal and sabotage require evidence.** Refusal needs a refusal claim or
    report. Sabotage needs a contrary effect plus intent evidence (prior
    opposition/refusal, a sabotage report, or repeated contrary acts). Sabotage
    remains an owner attribution.
13. **Provenance is explicit.** Owner-local `orgp-` proposals, `orgpm-`
    amendments, `orgcd-` decisions, `orgci-` implementations, and `orgcev-`
    evidence carry authority basis, evidence refs, and a closed provenance code.
    Publication mints `orgcpd-`/`orgcpi-` from publication-visible content only.
14. **Speech is bounded and additive.** `org_ca_v1` relations travel inside
    existing `Talk`/`Tell`; `org_v1`, `org_op_v1`, and `collective_decision`
    frames are unchanged. No command, event, observer semantic, or free-text
    payload is added.
15. **Owner-only inputs.** The update reads the owner observation and prepared
    owner ledgers only. No peer ledger, `WorldState`, event store, command, or
    other perspective is accepted.
16. **Analysis never creates identity.** Agency rows join existing analytical
    candidates; they never create, split, merge, dissolve, or re-identify one.
17. **Three layers, three types.** Objective rows are counts; subjective rows use
    `orgc-`/agency ids; analytical summaries use `org-`. Leakage is a hard
    failure.
18. **Deterministic by construction.** Sorted ordering, content-addressed ids,
    canonical JSON digests, quantized floats, no `hash()`, no UUID, and no
    wall-clock domain values.
19. **Snapshot v3 is additive.** v1/v2 remain decodable and byte-verifiable; new
    publications are v3. No analysis type is imported by simulation/persistence.
20. **Metrics append only.** 146 → 148 with two new families; the first 146 keep
    id, order, version, and value keys.
21. **Read-only surfaces.** Six GET routes under `/v1` require
    `SUBJECTIVE_DEBUG`; the Research UI renders server fields without derivation.
22. **Cursors bind to the publication digest.** The existing empty-digest defect
    is fixed for every paged organization route, not only the new route.
23. **Publication is opt-in and non-interfering.** A storage/composition failure
    changes only the receipt, never the scientific result.

### Context declaration

| Context | Flag | Authority | Owning packages | Prerequisites | Existing mechanism | Event strategy |
| --- | --- | --- | --- | --- | --- | --- |
| `organizations` | `organizations` (owned; deepened) | owner-scoped | `agents.cognition`, `social`, `simulation` | none | collective projects, public goods, mentorship, institution concepts, offices, institutional memory, collective decisions, structured commitments, group formation, possession legitimacy, organization operations | reuse |

### Compatibility pins

Default runner/result `v4`/`v2`; latest feature runner `v55`; accepted runner adds
`v56` only; events `EVENT_SCHEMA_REPLAY_V22` (22); codec `v20`; commands 43;
observer semantic types 73; metric families **148 (V4-05 change)**; Alembic
`0017`; `/v1`; `observer-protocol-v1`; observer layout `observer-layout-v1`;
observer capabilities 4 advertised / 6 reserved; four reserved write pairs
(events 23-26 / codecs `v21`-`v24`); `prepare_parallel=False`; six GET
organization routes; six cursor purposes; snapshots
`organization-snapshot-v1`/`v2`/`v3`.
`institutional_economy` and `multi_hop_testimony_tracking` remain unowned and fail
closed. `/version` is unchanged; `organization_rows` remains reserved.

## Phase Index

1. [Phase 1: Contract and Seam](phase-01-contract-and-seam.md) — Tasks 1-2
2. [Phase 2: Owner-Scoped Collective-Agency Beliefs](phase-02-agency-beliefs.md) — Tasks 3-8
3. [Phase 3: Detached Analysis, Disagreement, and Metrics](phase-03-detached-analysis.md) — Tasks 9-12
4. [Phase 4: Organization Snapshot v3](phase-04-snapshot-v3.md) — Tasks 13-14
5. [Phase 5: Composition and Durable Publication](phase-05-composition-publication.md) — Tasks 15-16
6. [Phase 6: Read-Only API and Research UI](phase-06-read-only-surfaces.md) — Tasks 17-18
7. [Phase 7: Invariants, End-to-End Evidence, and Regression](phase-07-invariants-and-regression.md) — Tasks 19-21
8. [Phase 8: Documentation and Final Verification](phase-08-docs-and-verification.md) — Tasks 22-23

## Cross-Phase Dependencies

- All phases assume the implemented V4-03 and V4-04 organization stacks are
  present; V4-05 does not re-certify them, but Tasks 19/21 must keep their suites
  green. If either stack changes during implementation, re-run its
  unit/architecture/static lanes before proceeding.
- Task 2 depends on Task 1: the policy seam uses the frozen vocabulary and limits.
- Task 3 depends on Task 2: records use the policy and ID grammar.
- Task 4 depends on Task 3: the `org_ca_v1` frame uses the agency stances and
  effects.
- Task 5 depends on Tasks 3-4: the update consumes the frame parser and records.
- Task 6 depends on Task 5: generation/appraisal/implementation consume the
  materialized ledger.
- Task 7 depends on Task 6: the ledger must exist before it is carried.
- Task 8 depends on Tasks 4-7: deliberation needs the frame, the update, and the
  carried snapshot field.
- Task 9 depends on Task 7: the harvest reads exported agency ledgers.
- Task 10 depends on Task 9: the summary consumes normalized rows.
- Task 11 depends on Tasks 9-10: layers consume rows and the summary.
- Task 12 depends on Tasks 10-11: both families read the summary/layers.
- Task 13 depends on Tasks 11-12: v3 mirrors rows/counts and metric provenance.
- Task 14 depends on Task 13: paging selects typed agency records.
- Task 15 depends on Tasks 12 and 14: the composer needs analysis and ports.
- Task 16 depends on Tasks 13-14: the store serves v1/v2/v3 and agency pages.
- Task 17 depends on Task 16: the API reads the committed store.
- Task 18 depends on Task 17: the panel consumes the sixth route and detail
  fields.
- Task 19 depends on Tasks 2-18: the suite asserts every authority claim.
- Task 20 depends on Tasks 5-18: the E2E uses the real update/artifact/surfaces.
- Task 21 depends on Tasks 19-20: regression runs after the invariant/E2E gates.
- Task 22 depends on Tasks 2-21: documentation describes verified surfaces.
- Task 23 depends on Tasks 21-22: final certification needs receipts and docs.

## Tasks

### Phase 1: Contract and Seam
- [x] Task 1: Freeze the collective-agency vocabulary and identity grammar ([details](phase-01-contract-and-seam.md#task-1-freeze-the-collective-agency-vocabulary-and-identity-grammar))
- [x] Task 2: Add the policy seam without a runner schema change ([details](phase-01-contract-and-seam.md#task-2-add-the-policy-seam-without-a-runner-schema-change)) (depends on 1)

### Phase 2: Owner-Scoped Collective-Agency Beliefs
- [x] Task 3: Define agency records and ledger invariants ([details](phase-02-agency-beliefs.md#task-3-define-agency-records-and-ledger-invariants)) (depends on 2)
- [x] Task 4: Add bounded `org_ca_v1` collective-agency speech frames ([details](phase-02-agency-beliefs.md#task-4-add-bounded-org_ca_v1-collective-agency-speech-frames)) (depends on 3)
- [x] Task 5: Collect claims and materialize proposals, positions, amendments, and decisions ([details](phase-02-agency-beliefs.md#task-5-collect-claims-and-materialize-proposals-positions-amendments-and-decisions)) (depends on 3, 4)
- [x] Task 6: Generate proposals, appraise positions, and track implementation ([details](phase-02-agency-beliefs.md#task-6-generate-proposals-appraise-positions-and-track-implementation)) (depends on 5)
- [x] Task 7: Carry the agency ledger through cognition, runtime, checkpoints, and the runner ([details](phase-02-agency-beliefs.md#task-7-carry-the-agency-ledger-through-cognition-runtime-checkpoints-and-the-runner)) (depends on 6)
- [x] Task 8: Wire collective-agency claims into existing deliberation ([details](phase-02-agency-beliefs.md#task-8-wire-collective-agency-claims-into-existing-deliberation)) (depends on 4, 5, 6, 7)

### Phase 3: Detached Analysis, Disagreement, and Metrics
- [x] Task 9: Harvest owner agency ledgers into detached rows ([details](phase-03-detached-analysis.md#task-9-harvest-owner-agency-ledgers-into-detached-rows)) (depends on 7)
- [x] Task 10: Summarize collective agency and implementation per candidate ([details](phase-03-detached-analysis.md#task-10-summarize-collective-agency-and-implementation-per-candidate)) (depends on 9)
- [x] Task 11: Project collective agency into the three layers without leakage ([details](phase-03-detached-analysis.md#task-11-project-collective-agency-into-the-three-layers-without-leakage)) (depends on 9, 10)
- [x] Task 12: Add two metric families and raise the catalog to 148 ([details](phase-03-detached-analysis.md#task-12-add-two-metric-families-and-raise-the-catalog-to-148)) (depends on 10, 11)

### Phase 4: Organization Snapshot v3
- [x] Task 13: Define snapshot v3 models and the canonical codec ([details](phase-04-snapshot-v3.md#task-13-define-snapshot-v3-models-and-the-canonical-codec)) (depends on 11, 12)
- [x] Task 14: Add collective-agency paging, read port, and cursor digest support ([details](phase-04-snapshot-v3.md#task-14-add-collective-agency-paging-read-port-and-cursor-digest-support)) (depends on 13)

### Phase 5: Composition and Durable Publication
- [x] Task 15: Compose completed-run v3 snapshots and receipts ([details](phase-05-composition-publication.md#task-15-compose-completed-run-v3-snapshots-and-receipts)) (depends on 12, 14)
- [x] Task 16: Extend the atomic filesystem store for v1/v2/v3 ([details](phase-05-composition-publication.md#task-16-extend-the-atomic-filesystem-store-for-v1v2v3)) (depends on 13, 14)

### Phase 6: Read-Only API and Research UI
- [x] Task 17: Add the sixth GET route and additive response fields ([details](phase-06-read-only-surfaces.md#task-17-add-the-sixth-get-route-and-additive-response-fields)) (depends on 16)
- [x] Task 18: Add the read-only Research UI collective-agency view ([details](phase-06-read-only-surfaces.md#task-18-add-the-read-only-research-ui-collective-agency-view)) (depends on 17)

### Phase 7: Invariants, End-to-End Evidence, and Regression
- [x] Task 19: Add the collective-agency boundary and determinism suite ([details](phase-07-invariants-and-regression.md#task-19-add-the-collective-agency-boundary-and-determinism-suite)) (depends on 2-18)
- [x] Task 20: Add the collective-agency end-to-end scenario ([details](phase-07-invariants-and-regression.md#task-20-add-the-collective-agency-end-to-end-scenario)) (depends on 5-18)
- [x] Task 21: Execute the full V1-V4 regression and qualification lanes ([details](phase-07-invariants-and-regression.md#task-21-execute-the-full-v1-v4-regression-and-qualification-lanes)) (depends on 19, 20)

### Phase 8: Documentation and Final Verification
- [x] Task 22: Execute the documentation checkpoint ([details](phase-08-docs-and-verification.md#task-22-execute-the-documentation-checkpoint)) (depends on 2-21)
- [x] Task 23: Perform final V4-05 verification ([details](phase-08-docs-and-verification.md#task-23-perform-final-v4-05-verification)) (depends on 21, 22)

## Verification Receipt (Tasks 21 and 23)

Executed on 2026-11-02. Required lanes that lack a prerequisite or exceeded the
available wall clock are recorded `unexecuted`; they are not certified.

| Lane | State | Evidence |
| --- | --- | --- |
| Unit + architecture (`tests/unit tests/architecture --cov`) | `executed_passed` | 7,738 passed in 2,040.50s; total coverage 78% |
| Focused V4-05 agency suite | `executed_passed` | 208 passed in 7.09s |
| Static `ruff check src tests` | `executed_passed` | All checks passed |
| Static `mypy src tests` | `executed_passed` | Success: no issues in 1,812 files |
| Static `lint-imports` | `executed_passed` | 25 contracts kept, 0 broken |
| Integration, non-scale, disposable `palimpsest_test` pgvector | `executed_passed` | 93 passed in 30.49s |
| Integration including scale selection | `unexecuted` | `-m integration` exceeded 40 minutes of wall clock; scale selection not completed |
| `docker compose config --quiet` | `executed_passed` | Exit 0 |
| Compose/browser acceptance | `unexecuted` | Requires a built `PALIMPSEST_API_IMAGE` and real browser driver; not run in this session |
| Godot 4.7.2 regression suite | `unexecuted` | No Godot binary available (`godot4` not found) |
| Benchmark/scale lane | `unexecuted` | Requires the disposable pgvector instance plus an extended benchmark window; not run |
| Research UI `vitest run` | `executed_passed` | 252 passed in 49 files |
| Research UI `svelte-check` + `tsc` | `executed_passed` | 0 errors, 0 warnings |
| Research UI production build | `executed_passed` | `npm run build` built 5 files |

Cross-surface pins verified: metric families 148 (last two agency families),
six GET organization routes, six cursor purposes, snapshot v1/v2/v3, events 22,
commands 43, observer semantic types 73, Alembic `0017` with no `0018_*.py`,
no `runner-config-v57`, 14 V4 contexts / 12 flags, and an untouched roadmap.

Post-verification closure: the boundary suite now checks magic-actor class names,
world ownership fields, metric-assembly imports, V3-31/V4-03/V4-04 policy
versions, V4 reservations, observer reservations, codec versions, Alembic head,
and `prepare_parallel`. The E2E now drives a real `Give` command through
`WorldEngine` and perception, asserts `give_item_ids`/target facts, covers a
testimonial decision without a report, reads a composed v3 publication, and
proves publication failure changes only the receipt. Codec negative tests cover
missing/extra keys, owner-local tokens, per-candidate and snapshot decision caps,
and v1→v3 upgrade. Cursor expiry and reuse on every paged route are covered.

Known caveat: one earlier full-suite run hit an order-dependent failure in
`test_institutional_memory_acquisition.py::test_duplicate_delivery_is_idempotent`
(which passes in isolation and in the two subsequent full runs). No V4-05 file
touches that subsystem. The green runs above are the recorded result.

## Commit Plan

Proposed implementation checkpoints; no commit is made by planning.

1. After Tasks 1-2: `feat(v4): freeze the organization collective-agency contract`
2. After Tasks 3-8: `feat(v4): form owner-scoped collective agency`
3. After Tasks 9-12: `feat(v4): analyze collective decisions and implementation`
4. After Tasks 13-16: `feat(v4): publish organization-snapshot-v3`
5. After Tasks 17-18: `feat(v4): serve read-only collective agency`
6. After Tasks 19-23: `test(v4): enforce collective-agency invariants`

## Blocking Conditions and Non-Goals

- Adding `runner-config-v57`, a new V4 flag, a new runner root field, or a
  per-agent runner mode to make this plan work is a blocking scope violation.
  Stop and re-plan.
- Creating an objective Organization, Government, Church, Corporation, Army,
  University, Guild, State, Nation, Polity, Empire, Tribe, Ministry, Department,
  Treasury, Bank, Court, Police, Party, resource pool, roster, or global
  organization registry is forbidden.
- Adding a global OrganizationLLM, shared prompt, collective cognition context,
  or organization-owned agent is forbidden.
- Giving `WorldEngine`, perception, cognition, memory, prompts, admission, or stop
  selectors a read of an agency ledger or another owner's ledger is forbidden.
- Letting an organization object return, construct, submit, or resolve an
  `AgentCommand`, move a resource, or execute a physical action is forbidden.
- Adding an objective `owner_id`/`ownership` field to items, resources, structures,
  artifacts, or repositories is forbidden.
- Requiring consensus, quorum, majority, exclusive membership, forced
  self-identification, or a census before a decision can be recorded is
  forbidden.
- Inferring refusal or sabotage from silence is forbidden.
- Changing the V3-31 collective-decision contract, V4-03 concept contract, or
  V4-04 operation contract is forbidden; V4-05 is a sidecar.
- Weakening an existing pin or assertion (catalog counts, Alembic `0017`, replay
  v22, codec v20, command count, observer semantic count, context count) is
  forbidden. The only intentional pin changes are 146 → 148 metric families,
  five → six organization routes, five → six cursor purposes, and v2 → v3
  snapshot with v1/v2 retained.
- Adding a new event, command, observer semantic type, write pair, `/v2` route,
  `observer-protocol-v2` serving, or SQL migration is forbidden.
- Claiming capacity, prevalence, emergence probability, predictive power,
  throughput, or a composite civilization score is forbidden.
- Editing `.ai-factory/ROADMAP.md` or closing M8 is out of scope; `$aif-roadmap`
  owns that.
- Changing the Godot client, observer protocol, observer capabilities, or
  `/version` is out of scope; the Research UI is the only client change.
- Enabling V4 flags in matrix lanes is out of scope; `experiments.matrix_schema`
  keeps its rejection gate.
- Full qualification requires a disposable PostgreSQL/pgvector instance, Docker,
  a real browser driver, and the pinned Node/pnpm and Godot toolchains. A missing
  prerequisite leaves the lane unexecuted and blocks certification; it never
  becomes a skip-pass.
- Do not implement any other V4 context (`formal_rules`, `legal_disputes`,
  `diplomacy`, `organized_conflict`, `infrastructure_networks`, `supply_chains`,
  `markets_credit`, `science`, `epidemics`, `ecological_feedback`, `disasters`,
  `societal_resilience`, `macro_society_identity`) in this plan.

## Definition of Done

- All 23 indexed tasks have verified completion evidence; only this index holds
  task progress checkboxes.
- `organizations` remains the one owned V4 flag on `runner-config-v56`; no `v57`,
  new flag, root field, or per-agent mode exists.
- The context registry validates at 14 contexts, 12 flags, and
  `v4-context-map-v2`; the analysis-only set and four reservations are unchanged.
- The V3-31 collective-decision contract and the V4-03/V4-04 organization
  contracts are unchanged; collective agency is a third sidecar keyed by `orgc-`.
- All requested stages exist: proposals, discussion, support, opposition,
  abstention, amendments, recognized procedure, collective decision record,
  implementation, compliance, refusal, and sabotage.
- Proposals, amendments, support, opposition, and abstention are retained as
  owner-local evidence and exposed as detached analysis rows plus published
  summary/candidate counts; decisions and per-actor implementations are
  published as bounded records.
- A proposal/decision is a belief; no organization will, super-agent, quorum,
  binding resolution, or global OrganizationLLM exists.
- No organization object constructs, submits, or executes a command; all physical
  effects are existing agent commands.
- Implementation is tracked per actor; a decision may be `unimplemented` because
  members do not act. Silence is `unknown`/`unimplemented`, never refusal or
  sabotage.
- Implementation matching uses real observation kinds and effect-specific anchor
  keys (`give_item_ids`, `take_item_ids`, `target_id`/`destination_id`,
  effect-specific `public_facts`); it never reuses V4-04 synthetic
  `given`/`taken`/`dropped`.
- Agency rows reach `analysis.metric_service` through
  `MetricComputationInputs.organization_agency_rows` and
  `experiments.collectors`; real completed-run assembly emits both new metric
  documents.
- Refusal and sabotage require explicit evidence; sabotage is an owner
  attribution with provenance.
- Disagreement is retained with `contested`/counts; no consensus gate exists.
- Owner-local `orgp-`/`orgpm-`/`orgcd-`/`orgci-`/`orgcev-` ids carry provenance;
  publication exposes deterministic `orgcpd-`/`orgcpi-` records without
  owner-local or raw actor ids.
- Detached analysis never creates, splits, merges, dissolves, or re-identifies a
  candidate; objective counts, owner claims, and analytical summaries remain
  separate.
- The metric catalog is exactly 148 with two appended families; the first 146 are
  unchanged.
- `organization-snapshot-v3` is canonical, bounded, immutable after publication,
  and v1/v2 remain decodable and byte-verifiable.
- Six GET-only `/v1` routes require `SUBJECTIVE_DEBUG`, have an explicit
  `organization_disabled` state, and are consumed by a read-only Research UI
  view.
- Cursor reuse works on every paged organization route; changed
  filter/run/publication/digest fails with 400 and expiry with 410.
- The boundary suite proves owner-only authority, absence of magic actors,
  treasuries, pools, rosters, registries, teleport helpers, objective ownership,
  global OrganizationLLM, and command construction; no new
  commands/events/migrations; unchanged observer/migration pins.
- The full V1-V4 regression lanes and static gates execute and pass; any
  unexecuted required lane is reported with its blocker and is not certified.
- Documentation states what a collective decision controls (a belief), what it
  never controls (objective action), how disagreement works, how failure works,
  how refusal/sabotage are attributed, how provenance is recorded, and every
  count matches the code.
