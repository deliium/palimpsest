<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-04 Organization Operational State

Mode: ultra
Branch: main
Created: 2026-10-31
Plan identifier: `v4-04-organization-operations`
Status: planned; no task is implemented. The bundle is the implementation
contract for `$aif-implement`.

## Original Request

v4-04 organization operational state

Naming requirement:

Use `v4-04-organization-operations`.

Extend organizations with operational primitives.

Support socially recognized:

- organization-owned/controlled resources

- storage

- records

- membership admission

- membership departure

- role assignment

- procedural actions

- internal commitments

Keep objective physical possession separate from subjective/legal ownership.

Do not allow an Organization object to teleport resources or execute physical actions.

Agent-mediated actions must produce all physical effects.

Allow organizations to operate even when members disagree about:

- membership

- authority

- resource legitimacy

- procedures

Record provenance of decisions and actions.

## Settings

- Testing: yes; full strategy. Unit, architecture, determinism, integration,
  Compose/browser, Godot regression, Research UI, benchmark regression, and static
  gates, with coverage enabled for Python lanes.
- Logging: verbose, metadata-only. Bounded DEBUG flow/counts, INFO milestones,
  WARN incomplete evidence/truncation, ERROR safe codes. `PALIMPSEST_LOG_LEVEL`
  controls operational verbosity. No person sets, private content, payload
  surrogates, prompts, credentials, tokens, DSNs, memories, embeddings, utterance
  bodies, labels, or anchor payloads.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 22.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints are suggestions, not authorization to
  commit during planning.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-04-organization-operations`; the ultra bundle
  directory is `.ai-factory/plans/v4-04-organization-operations/`, phase files
  use `phase-NN-<slug>.md`, and `index.md` is the canonical entrypoint.
- Research source: `.ai-factory/RESEARCH.md` and `.ai-factory/research/` do not
  exist; no external research conclusions are invented.
- Execution: plan only. No implementation, commit, roadmap edit, or branch
  creation occurs in this invocation.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"
Rationale: V4-04 deepens the already-owned V4-03 `organizations` context on the
accepted `runner-config-v56` seam. This plan does not edit or close the roadmap;
`$aif-roadmap` must register V4-04 in M8.

## Requirements Reconciliation

Authority: the Original Request defines scope; `.ai-factory/ARCHITECTURE.md`
("Key Principles", "Capability ownership", "Important V3 seams", "Versioned
Extension Contract", V4-01/V4-02/V4-03 seams) and `.ai-factory/RULES.md`
constrain every edit; `.ai-factory/DESCRIPTION.md` and `.ai-factory/ROADMAP.md`
describe current state; completed V4-01/V4-02/V4-03 code, pins, and the
`tests/architecture/test_*organization*`/`test_v4_*` suites govern compatibility.
V4-04 owns no new V4 flag; it extends the owner-scoped `organizations` context and
may not create an objective organization actor, roster, treasury, resource pool,
registry, executor, or independent cognition engine.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-04 deepens the one owned V4 flag `organizations`; no other flag, `runner-config-v57`, new root field, or per-agent runner key is added | Original Request "Extend organizations"; `.ai-factory/ARCHITECTURE.md` "Capability ownership"; `src/simulation/runner_models.py` 305-322; `src/simulation/v4_architecture.py` 103-121 | Task 1/2 contract tests; Task 19 pins; Task 23 `v57` absence |
| Operational state is a second owner-scoped ledger keyed by existing `orgc-` ids; the V4-03 `OrganizationConcept`/`OrganizationConceptLedger` contract, identity, digest, status, and lineage are unchanged | Original Request list; `src/agents/cognition/organization_concepts.py` 1203-1550, 2880-3175; V4-03 plan decisions 3-9 | Task 3/5/6/7 tests; Task 6/19 concept/lineage preservation |
| Eight operational domains map one-to-one to the requested primitives: resource control, storage, record keeping, admission, departure, role assignment, procedure action, internal commitment | Original Request bullets; `organization_concepts.py` resource/procedure/record/commitment beliefs 810-971 | Task 1/3/5/9 domain tests |
| Control is a belief about legitimate access/use, not objective custody; objective possession stays `holder_id`/`location_id`/`custodian_repository_id`/`stored_quantity` | Original Request "Keep objective physical possession separate"; `src/world/models.py` 114-230; `src/world/production.py` 398-424; `src/world/artifacts.py` 314-350; `src/world/repositories.py` 148-280 | Task 6/19 objective-owner-field scan; Task 20 possession-unchanged test |
| No organization object can teleport a resource or execute an action; all physical effects are the existing 43 commands selected and submitted by agents | Original Request "Do not allow..."; `src/world/actions.py` 890-1004; `src/simulation/actions.py` 294-355; `src/simulation/engine.py` 3903-4025 | Task 8/19 no-teleport/no-`AgentCommand` scan; Task 20 physical-effect test |
| Admission, departure, and role assignment are bounded claims/decisions with authority provenance; they are never permissions and never change admission rules | Original Request; `.ai-factory/ARCHITECTURE.md` V3-30 office seam; `src/agents/cognition/offices.py` 213-220, 777-995 | Task 3/4/5/6/19 tests |
| Disagreement about membership, authority, resource legitimacy, or procedures is first-class: claims remain `disputed` with `contest_count`, both sides are retained, and operations are still recorded | Original Request "operate even when members disagree"; V4-03 `OrganizationMembershipStatus` 60-68 | Task 4/5/6/10/11/20 tests |
| Every decision and action carries provenance: owner-local `orgd-`/`orga-` ids, authority basis, evidence refs, and a closed provenance code; publication exposes deterministic `orgop-` records without owner-local ids | Original Request "Record provenance"; `.ai-factory/ARCHITECTURE.md` Key Principles 2 | Task 1/3/5/6/13/15/23 id tests |
| Explicit and disputed operational claims use bounded `org_op_v1` relations inside existing `Talk`/`Tell`; no new command, event, observer semantic type, or free-text payload | `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts"; V4-03 `organization_communication.py` 44-288 | Task 4/8 tests; Task 19 command/event pins |
| The operation ledger reads only the owner's observation and prepared owner ledgers; it never reads peer ledgers, `WorldState`, event stores, commands, or another owner's perspective | Original Request "Agent-mediated"; `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime" | Task 6/8/19 isolation tests; Task 20 owner-only test |
| Detached analysis joins operations to existing analytical candidates; operations never create, split, merge, dissolve, or re-identify a candidate | Original Request; V4-03 detection/identity/lineage contracts `organization_detection.py` 378-484, `organization_identity.py` 126-300, `organization_lineage.py` 146-269 | Task 10/11 tests; Task 20 status/lineage-unchanged test |
| Objective counts, owner-local operational claims, and analytical operation summaries remain three distinct types with hard leakage checks | Original Request; `.ai-factory/ARCHITECTURE.md` Key Principles 1; V4-03 `organization_layers.py` 226-248 | Task 12/19 leakage tests |
| The metric catalog grows from 144 to 146 by appending `organization_operations@1` and `organization_operation_authority@1`; the first 144 families keep id, order, version, and value keys | `src/analysis/specifications.py` 53, 218-221, 6204-6397, 6546-6574 | Task 13/19/23 exact pin checks |
| `organization-snapshot-v2` adds bounded operation records/counts; `organization-snapshot-v1` remains decodable and byte-verifiable | `.ai-factory/ARCHITECTURE.md` "Use accepted-set and exact-key-set schema evolution"; `organization_codec.py` 36-112, 331-469 | Task 14/19/23 v1/v2 codec tests |
| Access is five GET-only `/v1` routes requiring `SUBJECTIVE_DEBUG`; the four V4-03 routes keep their paths, and a fifth operations route is additive | `docs/research-api.md`; V4-03 `api/routes/organization.py` 138-366 | Task 17/19 route tests; Task 20 API read |
| Publication is opt-in, post-completion, atomic, quota-bounded, and isolated from scientific status; no new CLI flag or environment variable is added | V4-02/V3-39/V4-03 precedent; `research_runner/organization_composition.py` 73-135 | Task 15/16/20 receipts and failure-isolation tests |
| No SQL migration, new event, command, observer semantic type, write pair, `/v2` route, or `observer-protocol-v2` is added; Alembic stays `0017`, events 22, codec v20, commands 43, semantics 73 | `.ai-factory/ARCHITECTURE.md` requirements 4-6; `src/simulation/versioning.py` 99-139 | Task 19/23 pins |
| Required lanes must execute; a missing prerequisite is reported `unexecuted` with a prerequisite, never as a skip-pass | Plan Settings "Testing: yes; full strategy"; `docs/development.md`; `tests/compose/acceptance.py` | Task 21 three-state receipt; Task 23 audit |
| The roadmap is owned by `$aif-roadmap` and is not edited here | `.ai-factory/ARCHITECTURE.md` requirement 7 | Task 22/23 `git status` |

### Supported combinations and availability transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| Default runner config, all V4 flags off | V3/V4-02/V4-03-equivalent behavior | No operation ledger, policy, metric, publication, or route data | Task 2/8/20 flags-off tests |
| `organizations` enabled on v4 or v55 | Unchanged config | `v4_capability_requires_v56` before construction | Task 2 test |
| `organizations` enabled on v56, no V3 evidence | Valid run | Empty concept and operation ledgers; operation metrics `ABSENT`; no fabricated operation | Task 6/12 tests |
| Concept beliefs only | Structural anchors | Operation ledger empty; concept-only snapshot v2; operation summary `None` | Task 6/10/12 tests |
| Self-authored admission claim | Admission decision | `authority_basis=self_authored`; decision `orgd-`; no world permission | Task 4/5/6 tests |
| Peer claim, recognized office speaker | Role-authorized belief | `authority_basis=role_belief`; decision recorded; no permission | Task 5/6 test |
| Peer claim, supported collective decision | Decision-authorized belief | `authority_basis=decision_belief`; support/oppose counts copied | Task 5/6 test |
| Peer claim, no authority evidence | Unknown authority | Decision retained with `unknown_authority`; no forced rejection | Task 6/10 tests |
| Two contradictory admission/control claims | Dispute | Both sides retained; `stance=disputed`, `contest_count>0`; operations still recorded | Task 6/10/11/20 tests |
| Observed `given`/`item_stored`/`artifact_created` | Action provenance | Action record with `observed_effect` and the right domain/anchor | Task 5/6 test |
| Missing objective anchor | Unresolved reference | `anchor_kind=unknown`, `resolved=False`, `operation_anchor_unresolved`; no zero inference | Task 6/13/15 tests |
| Selected command outside the domain allowlist | Unsupported action | No operation action match; command unchanged; no world effect added | Task 8 test |
| Organization concept splits/merges | Predecessor operations | Operations stay with the retired predecessor; children start empty; lineage unchanged | Task 6/20 tests |
| Concept dissolves | Dissolved operations | Existing operations retained as `dissolved`/`former`; no new decisions | Task 5/6 test |
| Candidate exceeds 64 operations | Deterministic truncation | `operations_truncated`; no silent drop | Task 13/15 tests |
| Snapshot exceeds 4096 operations or 4 MiB | No publication | `organization_size_limit` | Task 13/15 tests |
| Duplicate publication id with different bytes | Existing publication untouched | `organization_publication_exists` | Task 16 test |
| v1 publication read by v2 reader | v1 artifact | Read-only summary/candidates/lineage with `operation_count=0` | Task 16 test |
| `PALIMPSEST_ORGANIZATION_ROOT` unset | API state unset | 503 `organization_disabled`; CLI receipt `disabled` | Task 17/20 tests |
| Cursor reused with changed filter/run/publication | No page served | 400 `organization_cursor_invalid`; expired 410 | Task 14/17 test |
| Run incomplete or publication failed | Scientific result unchanged | Receipt `unavailable`/`failed` only | Task 16/20 test |
| Required Compose/browser/Godot/benchmark lane with a missing prerequisite | No green certification | Recorded `unexecuted` with prerequisite | Task 21/23 |

## Architecture and Decisions

1. **One owned flag, one seam.** `organizations` already owns the V4 context and
   requires `runner-config-v56`. V4-04 adds no flag, runner schema, root field, or
   per-agent runner key; it adds only an internal cognition policy.
2. **A sidecar, not a concept rewrite.** `OrganizationOperationLedger` is a second
   owner-scoped ledger keyed by `orgc-`. The V4-03 concept contract, digest,
   status, identity, and lineage are untouched.
3. **Belief, not objective state.** Control, storage, records, admission,
   departure, assignment, procedure action, and commitment are beliefs about
   legitimacy and recognized acts. No `WorldEngine` entity, roster, treasury,
   pool, registry, or executor exists.
4. **Objective possession is separate.** `holder_id`, `location_id`,
   `custodian_repository_id`, and `stored_quantity` are the only objective
   custody/storage fields. A control belief cites them; it never changes them.
5. **No teleport, no executor.** Operational helpers classify existing commands;
   they never return, construct, or submit a command. Every physical effect is an
   ordinary `AgentCommand` admitted and resolved by the engine.
6. **Eight domains.** Resource control, storage, record keeping, admission,
   departure, role assignment, procedure action, internal commitment. No
   hard-coded Government/Church/Corporation/Army/University/Guild class.
7. **Admission/departure/assignment are claims.** They can be self-authored,
   role-authorized, decision-authorized, disputed, or unknown. They are never
   permissions and never change world admission rules.
8. **Disagreement is data.** Contradictory claims are retained with
   `stance=disputed` and `contest_count`; a single owner's claim is enough to
   record an operation, and no consensus gate exists.
9. **Provenance is explicit.** `orgd-` decisions and `orga-` actions carry
   authority basis, evidence refs, and a closed provenance code. Publication mints
   `orgop-` records from publication-visible content only.
10. **Speech is bounded and additive.** `org_op_v1` relations travel inside
    existing `Talk`/`Tell`; `org_v1` is unchanged. No command, event, observer
    semantic, or free-text payload is added.
11. **Owner-only inputs.** The update reads the owner observation and prepared
    owner ledgers only. No peer ledger, `WorldState`, event store, command, or
    other perspective is accepted.
12. **Analysis never creates identity.** Operations join existing analytical
    candidates; they never create, split, merge, dissolve, or re-identify one.
13. **Three layers, three types.** Objective rows are counts; subjective rows use
    `orgc-`; analytical summaries use `org-`. Leakage is a hard failure.
14. **Deterministic by construction.** Sorted ordering, content-addressed ids,
    canonical JSON digests, quantized floats, no `hash()`, no UUID, and no
    wall-clock domain values.
15. **Snapshot v2 is additive.** v1 remains decodable and byte-verifiable; new
    publications are v2. No analysis type is imported by simulation/persistence.
16. **Metrics append only.** 144 → 146 with two new families; the first 144 keep
    id, order, version, and value keys.
17. **Read-only surfaces.** Five GET routes under `/v1` require
    `SUBJECTIVE_DEBUG`; the Research UI renders server fields without derivation.
18. **Publication is opt-in and non-interfering.** A storage/composition failure
    changes only the receipt, never the scientific result.

### Context declaration

| Context | Flag | Authority | Owning packages | Prerequisites | Existing mechanism | Event strategy |
| --- | --- | --- | --- | --- | --- | --- |
| `organizations` | `organizations` (owned; deepened) | owner-scoped | `agents.cognition`, `social`, `simulation` | none | collective projects, public goods, mentorship, institution concepts, offices, institutional memory, collective decisions, structured commitments, group formation, possession legitimacy | reuse |

### Unchanged compatibility pins

Default runner/result `v4`/`v2`; latest feature runner `v55`; accepted runner adds
`v56` only; events `EVENT_SCHEMA_REPLAY_V22` (22); codec `v20`; commands 43;
observer semantic types 73; metric families **146 (V4-04 change)**; Alembic
`0017`; `/v1`; `observer-protocol-v1`; observer layout `observer-layout-v1`;
observer capabilities 4 advertised / 6 reserved; four reserved write pairs
(events 23-26 / codecs `v21`-`v24`); `prepare_parallel=False`.
`institutional_economy` and `multi_hop_testimony_tracking` remain unowned and fail
closed. `/version` is unchanged; `organization_rows` remains reserved.

## Phase Index

1. [Phase 1: Contract and Seam](phase-01-contract-and-seam.md) — Tasks 1-2
2. [Phase 2: Owner-Scoped Operational Beliefs](phase-02-operational-beliefs.md) — Tasks 3-8
3. [Phase 3: Detached Analysis, Disagreement, and Metrics](phase-03-detached-analysis.md) — Tasks 9-12
4. [Phase 4: Organization Snapshot v2](phase-04-snapshot-v2.md) — Tasks 13-14
5. [Phase 5: Composition and Durable Publication](phase-05-composition-publication.md) — Tasks 15-16
6. [Phase 6: Read-Only API and Research UI](phase-06-read-only-surfaces.md) — Tasks 17-18
7. [Phase 7: Invariants, End-to-End Evidence, and Regression](phase-07-invariants-and-regression.md) — Tasks 19-21
8. [Phase 8: Documentation and Final Verification](phase-08-docs-and-verification.md) — Tasks 22-23

## Cross-Phase Dependencies

- All phases assume the implemented V4-03 organization stack is present; V4-04
  does not re-certify V4-03, but Tasks 19/21 must keep its suites green. If V4-03
  changes during implementation, re-run its unit/architecture/static lanes before
  proceeding.
- Task 2 depends on Task 1: the policy seam uses the frozen vocabulary and limits.
- Task 3 depends on Task 2: records use the policy and ID grammar.
- Task 4 depends on Task 3: the `org_op_v1` frame uses the operational stances.
- Task 5 depends on Tasks 3-4: evidence collection consumes the frame parser and records.
- Task 6 depends on Task 5: materialization consumes the evidence bundle.
- Task 7 depends on Task 6: the ledger must exist before it is carried.
- Task 8 depends on Tasks 5-7: deliberation needs the frame, support helpers, the public update, and the carried snapshot field.
- Task 9 depends on Task 7: the harvest reads exported operation ledgers.
- Task 10 depends on Task 9: the summary consumes normalized rows.
- Task 11 depends on Tasks 9-10: layers consume rows and the summary.
- Task 12 depends on Tasks 10-11: both families read the analysis/summary.
- Task 13 depends on Tasks 11-12: v2 mirrors rows/counts and metric provenance.
- Task 14 depends on Task 13: paging selects typed operation records.
- Task 15 depends on Tasks 12 and 14: the composer needs analysis and ports.
- Task 16 depends on Tasks 13-14: the store serves v1/v2 and operation pages.
- Task 17 depends on Task 16: the API reads the committed store.
- Task 18 depends on Task 17: the panel consumes the fifth route and detail fields.
- Task 19 depends on Tasks 2-18: the suite asserts every authority claim.
- Task 20 depends on Tasks 5-18: the E2E uses the real update/artifact/surfaces.
- Task 21 depends on Tasks 19-20: regression runs after the invariant/E2E gates.
- Task 22 depends on Tasks 2-21: documentation describes verified surfaces.
- Task 23 depends on Tasks 21-22: final certification needs receipts and docs.

## Tasks

### Phase 1: Contract and Seam
- [x] Task 1: Freeze the operational vocabulary and identity grammar ([details](phase-01-contract-and-seam.md#task-1-freeze-the-operational-vocabulary-and-identity-grammar))
- [x] Task 2: Add the policy seam without a runner schema change ([details](phase-01-contract-and-seam.md#task-2-add-the-policy-seam-without-a-runner-schema-change)) (depends on 1)

### Phase 2: Owner-Scoped Operational Beliefs
- [x] Task 3: Define operational records and ledger invariants ([details](phase-02-operational-beliefs.md#task-3-define-operational-records-and-ledger-invariants)) (depends on 2)
- [x] Task 4: Add bounded `org_op_v1` operational speech frames ([details](phase-02-operational-beliefs.md#task-4-add-bounded-org_op_v1-operational-speech-frames)) (depends on 3)
- [x] Task 5: Collect operational evidence and derive decision/action provenance ([details](phase-02-operational-beliefs.md#task-5-collect-operational-evidence-and-derive-decisionaction-provenance)) (depends on 3, 4)
- [x] Task 6: Materialize the operation ledger and enforce caps ([details](phase-02-operational-beliefs.md#task-6-materialize-the-operation-ledger-and-enforce-caps)) (depends on 5)
- [x] Task 7: Carry the operation ledger through cognition, runtime, checkpoints, and the runner ([details](phase-02-operational-beliefs.md#task-7-carry-the-operation-ledger-through-cognition-runtime-checkpoints-and-the-runner)) (depends on 6)
- [x] Task 8: Wire claims and operational classification into existing deliberation ([details](phase-02-operational-beliefs.md#task-8-wire-claims-and-operational-classification-into-existing-deliberation)) (depends on 5, 6, 7)

### Phase 3: Detached Analysis, Disagreement, and Metrics
- [x] Task 9: Harvest owner operation ledgers into detached rows ([details](phase-03-detached-analysis.md#task-9-harvest-owner-operation-ledgers-into-detached-rows)) (depends on 7)
- [x] Task 10: Summarize operations and disagreement per candidate ([details](phase-03-detached-analysis.md#task-10-summarize-operations-and-disagreement-per-candidate)) (depends on 9)
- [x] Task 11: Project operations into the three layers without leakage ([details](phase-03-detached-analysis.md#task-11-project-operations-into-the-three-layers-without-leakage)) (depends on 9, 10)
- [x] Task 12: Add two metric families and raise the catalog to 146 ([details](phase-03-detached-analysis.md#task-12-add-two-metric-families-and-raise-the-catalog-to-146)) (depends on 10, 11)

### Phase 4: Organization Snapshot v2
- [x] Task 13: Define snapshot v2 models and the canonical codec ([details](phase-04-snapshot-v2.md#task-13-define-snapshot-v2-models-and-the-canonical-codec)) (depends on 11, 12)
- [x] Task 14: Add operation paging, read port, and cursor support ([details](phase-04-snapshot-v2.md#task-14-add-operation-paging-read-port-and-cursor-support)) (depends on 13)

### Phase 5: Composition and Durable Publication
- [x] Task 15: Compose completed-run v2 snapshots and receipts ([details](phase-05-composition-publication.md#task-15-compose-completed-run-v2-snapshots-and-receipts)) (depends on 12, 14)
- [x] Task 16: Extend the atomic filesystem store for v1/v2 ([details](phase-05-composition-publication.md#task-16-extend-the-atomic-filesystem-store-for-v1v2)) (depends on 13, 14)

### Phase 6: Read-Only API and Research UI
- [ ] Task 17: Add the fifth GET route and additive response fields ([details](phase-06-read-only-surfaces.md#task-17-add-the-fifth-get-route-and-additive-response-fields)) (depends on 16)
- [ ] Task 18: Add the read-only Research UI operations view ([details](phase-06-read-only-surfaces.md#task-18-add-the-read-only-research-ui-operations-view)) (depends on 17)

### Phase 7: Invariants, End-to-End Evidence, and Regression
- [ ] Task 19: Add the operational boundary and determinism suite ([details](phase-07-invariants-and-regression.md#task-19-add-the-operational-boundary-and-determinism-suite)) (depends on 2-18)
- [ ] Task 20: Add the operational end-to-end scenario ([details](phase-07-invariants-and-regression.md#task-20-add-the-operational-end-to-end-scenario)) (depends on 5-18)
- [ ] Task 21: Execute the full V1-V4 regression and qualification lanes ([details](phase-07-invariants-and-regression.md#task-21-execute-the-full-v1-v4-regression-and-qualification-lanes)) (depends on 19, 20)

### Phase 8: Documentation and Final Verification
- [ ] Task 22: Execute the documentation checkpoint ([details](phase-08-docs-and-verification.md#task-22-execute-the-documentation-checkpoint)) (depends on 2-21)
- [ ] Task 23: Perform final V4-04 verification ([details](phase-08-docs-and-verification.md#task-23-perform-final-v4-04-verification)) (depends on 21, 22)

## Commit Plan

Proposed implementation checkpoints; no commit is made by planning.

1. After Tasks 1-2: `feat(v4): freeze the organization operations contract`
2. After Tasks 3-8: `feat(v4): form owner-scoped organization operational state`
3. After Tasks 9-12: `feat(v4): analyze organization operations and authority`
4. After Tasks 13-16: `feat(v4): publish organization-snapshot-v2`
5. After Tasks 17-18: `feat(v4): serve read-only organization operations`
6. After Tasks 19-23: `test(v4): enforce organization operation invariants`

## Blocking Conditions and Non-Goals

- Adding `runner-config-v57`, a new V4 flag, a new runner root field, or a
  per-agent runner mode to make this plan work is a blocking scope violation.
  Stop and re-plan.
- Creating an objective Organization, Government, Church, Corporation, Army,
  University, Guild, State, Nation, Polity, Empire, Tribe, Ministry, Department,
  Treasury, Bank, Court, Police, Party, resource pool, roster, or global
  organization registry is forbidden.
- Giving `WorldEngine`, perception, cognition, memory, prompts, admission, or stop
  selectors a read of an operation ledger or another owner's ledger is forbidden.
- Letting an organization object return, construct, submit, or resolve an
  `AgentCommand`, move a resource, or execute a physical action is forbidden.
- Adding an objective `owner_id`/`ownership` field to items, resources, structures,
  artifacts, or repositories is forbidden.
- Requiring consensus, exclusive membership, forced self-identification, or a
  census before an operation can be recorded is forbidden.
- Changing the V4-03 concept contract, identity, digest, status, or lineage
  semantics is forbidden; operations are a sidecar.
- Weakening an existing pin or assertion (catalog counts, Alembic `0017`, replay
  v22, codec v20, command count, observer semantic count, context count) is
  forbidden. The only intentional pin change is 144 -> 146 metric families.
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
- The V4-03 concept ledger contract, identity, digest, status, and lineage are
  unchanged; operations are a sidecar keyed by `orgc-`.
- All eight operational domains exist: resource control, storage, record keeping,
  membership admission, membership departure, role assignment, procedure action,
  internal commitment.
- Objective physical possession remains `holder_id`/`location_id`/
  `custodian_repository_id`/`stored_quantity`; no objective ownership field is
  added.
- No organization object can teleport resources or execute physical actions; all
  physical effects are existing agent commands.
- Admission, departure, and role assignment are claims with provenance, never
  permissions. Temporary admissions carry an explicit `expires_tick` and
  transition to `former` with `operation_expired`; expiry is never silent.
- Disagreement is retained with `disputed`/`contest_count`; operations are still
  recorded; no consensus gate exists.
- Decisions and actions carry owner-local `orgd-`/`orga-` ids, authority basis,
  evidence refs, and a closed provenance code; publication exposes deterministic
  `orgop-` records without owner-local ids.
- Detached analysis never creates, splits, merges, dissolves, or re-identifies a
  candidate; objective counts, owner claims, and analytical summaries remain
  separate.
- The metric catalog is exactly 146 with two appended families; the first 144 are
  unchanged.
- `organization-snapshot-v2` is canonical, bounded, immutable after publication,
  and v1 remains decodable and byte-verifiable.
- Five GET-only `/v1` routes require `SUBJECTIVE_DEBUG`, have an explicit
  `organization_disabled` state, and are consumed by a read-only Research UI view.
- The boundary suite proves owner-only authority, absence of magic actors,
  treasuries, pools, rosters, registries, teleport helpers, and objective
  ownership; no new commands/events/migrations; unchanged observer/migration
  pins.
- The full V1-V4 regression lanes and static gates execute and pass; any
  unexecuted required lane is reported with its blocker and is not certified.
- Documentation states what an organization controls (a belief), what it never
  controls (objective custody), how disagreement works, how provenance is
  recorded, and every count matches the code.
