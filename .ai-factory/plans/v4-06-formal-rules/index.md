<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-06 Formal Social Rules

Mode: ultra
Branch: main
Created: 2026-11-02
Plan identifier: `v4-06-formal-rules`
Status: implementation complete and verified on 2026-11-03 (23/23 tasks). All
required lanes executed and passed; V4-06 is certified.

## Original Request

v4-06 formal social rules

Naming requirement:

Use `v4-06-formal-rules`.

Extend V2/V3 norms into explicit socially recognized rules.

Model the possible progression:

habit  
→ expectation  
→ norm  
→ documented rule  
→ recognized enforcement procedure

WorldEngine must NOT enforce social rules as physical laws.

Distinguish:

physical impossibility

from

social prohibition.

Rules may have:

- scope
    
- proponents
    
- recognized authority
    
- written representation
    
- expected sanction
    
- exceptions
    
- historical versions
    
Agents may:

- follow
    
- violate
    
- challenge
    
- reinterpret
    
- ignore
    
Allow competing rule systems.

## Settings

- Testing: yes; full strategy. Unit, architecture, determinism, integration,
  Compose/browser, Godot regression, Research UI, benchmark regression, and
  static gates, with coverage enabled for Python lanes.
- Logging: verbose, metadata-only. Bounded DEBUG flow/counts, INFO milestones,
  WARN incomplete evidence/truncation, ERROR safe codes. `PALIMPSEST_LOG_LEVEL`
  controls operational verbosity. No rule content, scope anchors, person sets,
  private content, payload surrogates, prompts, credentials, tokens, DSNs,
  memories, embeddings, utterance bodies, labels, or artifact payloads.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 22.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints are suggestions, not authorization to
  commit during planning.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-06-formal-rules`; the ultra bundle directory is
  `.ai-factory/plans/v4-06-formal-rules/`, phase files use
  `phase-NN-<slug>.md`, and `index.md` is the canonical entrypoint.
- Research source: `.ai-factory/RESEARCH.md` and `.ai-factory/research/` do not
  exist; no external research conclusions are invented.
- Execution: plan only. No implementation, commit, roadmap edit, or branch
  creation occurs in this invocation.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"
Rationale: V4-06 owns the already-declared owner-scoped `formal_rules` V4
context on the accepted `runner-config-v56` seam, extending V2/V3 norms and
conventions without adding world law. This plan does not edit or close the
roadmap; `$aif-roadmap` must register V4-06 in M8.

## Requirements Reconciliation

Authority: the Original Request defines scope; `.ai-factory/ARCHITECTURE.md`
("Key Principles", "Capability ownership", "Important V3 seams", "Versioned
Extension Contract", V4-01 through V4-05 seams) and `.ai-factory/RULES.md`
constrain every edit; `.ai-factory/DESCRIPTION.md` and `.ai-factory/ROADMAP.md`
describe current state; completed V2/V3 norm, convention, institution, office,
durable-record, organization, operation, and collective-agency code plus the
`tests/architecture/test_*organization*`, `test_v4_*`, and `test_*norm*` suites
govern compatibility. V4-06 owns exactly one new V4 capability flag,
`formal_rules`; it may not create an objective law object, rule engine, sanction
engine, court, police, government, jurisdiction, or global rule registry.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-06 owns the declared `formal_rules` context; no other V4 flag, `runner-config-v57`, new root field, or per-agent runner key is added | Original Request "formal social rules"; `.ai-factory/ARCHITECTURE.md` "Capability ownership"; `src/simulation/v4_architecture.py` 122-135; `src/simulation/runner_models.py` 305-323, 1112-1160 | Task 1/2 tests; Task 19 pins; Task 23 `v57` absence |
| `formal_rules` is owner-scoped, uses existing events, and has no prerequisite context; it remains separate from `organizations` | `src/simulation/v4_architecture.py` 122-135; `src/simulation/versioning.py` 77-90 | Task 1/2/19 tests |
| Norms, conventions, institution concepts, offices, durable records, and organization authority are inputs; none is rewritten | Original Request "Extend V2/V3 norms"; `social_norms.py` 29, 608-751, 1303; `social_conventions.py` 30, 553-680, 1680; `institution_concepts.py` 55, 1388; `offices.py` 66, 2477; `world/artifacts.py` 78-110; `organization_concepts.py` 1483 | Task 6/7/19 tests |
| The progression is habit → expectation → norm → documented rule → recognized enforcement, monotone within one owner rule | Original Request progression; `NormStatus` 107-112; `ConventionBelief` 401; `InstitutionConceptStatus` 167 | Task 1/3/6/10 tests |
| A rule constrains social behavior only; physical impossibility stays with `WorldEngine` admission and is never represented as a rule | Original Request "WorldEngine must NOT enforce social rules as physical laws"; `src/world/actions.py`; `src/simulation/actions.py`; `src/simulation/engine.py` | Task 1/19 physical-distinction tests; Task 20 E2E |
| Rules carry scope, proponents, recognized authority, written representation, expected sanction, exceptions, and historical versions | Original Request bullet list; `offices.py` 455-778; `formal-rules.v1` design in Task 1/4 | Task 3/4/6/7/10 tests |
| Agents may follow, violate, challenge, reinterpret, or ignore a rule; these are owner responses or claims, never objective compliance | Original Request bullet list; `NormResponse` 115-125; V3-31 compliance precedent | Task 4/7/11/20 tests |
| Competing rule systems coexist; no precedence, union, or consensus gate resolves them | Original Request "Allow competing rule systems"; V4-03 overlap precedent; `organization_detection.py` 378-484 | Task 6/10/11/20 tests |
| A rule is an owner belief about a socially recognized constraint, not a world permission or prohibition | `.ai-factory/ARCHITECTURE.md` "Important V3 seams" (V3-29 through V3-31); `.ai-factory/RULES.md` axioms 1 and 3 | Task 1/3/19 no-law-object tests |
| No `WorldEngine`, perception, admission, stop selector, or memory service reads a formal-rule ledger | Original Request "must NOT enforce"; `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime" | Task 8/19 import scans; Task 20 physical-effect test |
| No helper constructs, submits, resolves, or executes an `AgentCommand`; enforcement and sanctions remain ordinary agent actions | Original Request; `src/world/actions.py` 890-1004; `src/simulation/actions.py` 294-355 | Task 8/19 command scans; Task 20 E2E |
| Bounded `fr_v1` claims travel inside existing `Talk`/`Tell`; no new command, event, observer semantic type, or free-text payload | `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts"; `organization_agency_communication.py` 54-398 | Task 5/8 tests; Task 19 pins |
| Written representation references an observed durable record/repository revision; no new artifact kind, record genre, or objective law field is added | `world/artifacts.py` 78-110, 315; `world/repositories.py` 149; `agents/cognition/artifacts.py` 193, 330 | Task 4/6/19 boundary tests |
| Expected sanction is a belief; no automatic sanction or policy engine exists | `v4_architecture.py` formal_rules non-goals 131-135; `social_norms.py` `_record_sanction`/`_enforce` | Task 4/7/19 tests |
| The ledger reads only the owner observation and prepared owner ledgers; it never reads peer ledgers, `WorldState`, event stores, commands, or another perspective | Original Request; `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime" | Task 6/8/19 isolation tests; Task 20 owner-only test |
| Detached analysis joins formal-rule rows to new analytical rule-system candidates; it never creates an objective rule or changes an organization candidate | Original Request; V4-03 detection/identity/lineage contracts; `organization_layers.py` 226-303 | Task 9/10/11 tests; Task 20 identity-unchanged test |
| Objective counts, owner claims, and analytical summaries remain three distinct types with hard leakage checks | `.ai-factory/ARCHITECTURE.md` Key Principles 1; `organization_layers.py` 226-303 | Task 11/19 leakage tests |
| The metric catalog grows from 148 to 151 by appending `formal_rule_development@1`, `formal_rule_authority@1`, and `formal_rule_response@1`; the first 148 families keep id, order, version, and value keys | `src/analysis/specifications.py` 52-53, 218-225; `src/analysis/metric_service.py` 1431-1558 | Task 12/19/23 exact pin checks |
| `formal-rule-snapshot-v1` is a new independent artifact; organization snapshots v1/v2/v3 remain byte-verifiable and unchanged | `.ai-factory/ARCHITECTURE.md` "Use accepted-set and exact-key-set schema evolution"; `organization_codec.py` 820-886 | Task 13/19/23 snapshot tests |
| Access is six GET-only `/v1` formal-rule routes requiring `SUBJECTIVE_DEBUG`; the six organization routes keep their paths | `docs/research-api.md` line 30; `api/routes/organization.py` 168-485 | Task 17/19 route tests; Task 20 API read |
| Cursors bind to the publication digest and query fingerprint; changed run/filter/publication/digest fails with 400 and expiry with 410 | V4-05 cursor repair precedent; `organization_ports.py` 169-232 | Task 14/17 cursor tests |
| Publication is opt-in, post-completion, atomic, quota-bounded, and isolated from scientific status; new CLI flags/env root follow the organization precedent | V4-02/V3-39/V4-03/V4-04/V4-05 precedent; `research_runner/organization_composition.py` 65-135 | Task 15/16/20 receipts and failure-isolation tests |
| No SQL migration, new event, command, observer semantic type, write pair, `/v2` route, or `observer-protocol-v2` is added; Alembic stays `0017`, events 22, codec v20, commands 43, semantics 73 | `.ai-factory/ARCHITECTURE.md` requirements 4-6; `src/simulation/versioning.py` 99-139 | Task 19/23 pins |
| Formal-rule rows flow through `MetricComputationInputs.formal_rule_rows`, `experiments.collectors`, and `analysis.metric_service`; the new families are emitted by real completed-run assembly | `.ai-factory/ARCHITECTURE.md` "analysis is read-only"; `metric_service.py` 311-313, 1431-1558; `experiments/collectors.py` 779-817 | Task 9/12 tests; Task 20 metric assembly; Task 21 metric-service lane |
| The carried ledger reaches `Perspective` through `build_perspective` and `SimulationRunnerResult` validates ordered ledger sequences | `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime"; `src/simulation/perception.py` 141, 350; `src/simulation/runner_models.py` 6646-6677 | Task 8 tests; Task 19 carry scan |
| Required lanes must execute; a missing prerequisite is reported `unexecuted` with a prerequisite, never as a skip-pass | Plan Settings "Testing: yes; full strategy"; `docs/development.md`; `tests/compose/acceptance.py` | Task 21 three-state receipt; Task 23 audit |
| The roadmap is owned by `$aif-roadmap` and is not edited here | `.ai-factory/ARCHITECTURE.md` requirement 7 | Task 22/23 `git status` |

### Supported combinations and availability transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| Default runner config, all V4 flags off | V3/V4-02 through V4-05-equivalent behavior | No formal-rule ledger, policy, metric, publication, or route data | Task 2/8/20 flags-off tests |
| `formal_rules` enabled on v4 or v55 | Unchanged config | `v4_capability_requires_v56` before construction | Task 2 test |
| `formal_rules` enabled on v56, no V2/V3 evidence | Valid run | Empty formal-rule ledger; formal-rule metrics `ABSENT`; no fabricated rule | Task 6/12 tests |
| Norm belief only | Habit/expectation/norm stage | Rule candidate with no written representation and no recognized enforcement | Task 6/10 test |
| Convention belief only | Habit stage | Rule candidate; no prohibition claim until a norm or claim exists | Task 6 test |
| Active norm plus observed durable record | Documented rule | Stage `documented`; written artifact/revision recorded; no enforcement | Task 6/20 test |
| Documented rule plus recognized office/organization/procedure authority with recurrence 2 | Recognized enforcement | Stage `recognized_enforcement`; enforcement procedure ref retained | Task 6/10 test |
| Two owners assert opposite constraints on one scope/action | Competing systems | Two `frs-` systems and two candidates; contested status; no precedence | Task 6/10/11/20 tests |
| Rule amended in order | New version | Version increments; prior version retained; supersedes link set | Task 4/6/10 tests |
| Amendment out of order | Prior version | `formal_rule_version_out_of_order`; no silent jump | Task 6 test |
| Owner follows a rule | Follow response | `frr-` response `follow`; no command created or suppressed | Task 7/20 tests |
| Owner violates a rule | Violate response | `frr-` response `violate`; the real command is still admitted if physically possible | Task 7/19/20 tests |
| Owner challenges a rule | Challenge claim | Contest count increments; rule becomes `contested` | Task 5/7/11 tests |
| Owner reinterprets a rule | Reinterpretation | New version or position with authority/provenance; no world change | Task 5/6 test |
| Owner ignores a rule | Ignore response | `frr-` response `ignore`; no sanction is inferred | Task 7/19 test |
| Socially prohibited but physically possible command | Rule belief retained | Ordinary command admitted; rule never reaches admission | Task 19/20 test |
| Physically impossible command | Existing admission rejection | Unchanged error; no rule attribution | Task 19 test |
| Expected sanction recorded | Sanction belief | `formal_rule_sanction_histogram` increments; no automatic sanction action | Task 7/10/19 tests |
| Exception recorded | Exception belief | Exception retained; prohibition remains; no permission granted | Task 4/7/10 tests |
| Written record damaged or missing | Degraded representation | `representation_status` `damaged`/`missing`; rule survives with provenance | Task 6/10 test |
| Peer `fr_v1` claim under a matching system | Owner-local claim | Evidence/position with `communicated` provenance; no rule copy or world change | Task 5 test |
| Peer `fr_v1` claim with no matching system | Orphaned claim | `orphaned_rule_system`; no rule minted | Task 5 test |
| Candidate exceeds 64 rules | Deterministic truncation | `formal_rule_truncated`; no silent drop | Task 13/15 tests |
| Snapshot exceeds 4096 rules / 8192 versions / 4 MiB | No publication | `formal_rule_size_limit` | Task 13/15 tests |
| Duplicate publication id with different bytes | Existing publication untouched | `formal_rule_publication_exists` | Task 16 test |
| `PALIMPSEST_FORMAL_RULE_ROOT` unset | API state unset | 503 `formal_rule_disabled`; CLI receipt `disabled` | Task 17/20 tests |
| Cursor reused with same filter/run/publication/digest | Same page | 200; digest matches | Task 14/17 test |
| Cursor reused with changed filter/run/publication/digest | No page served | 400 `formal_rule_cursor_invalid`; expired 410 | Task 14/17 test |
| Run incomplete or publication failed | Scientific result unchanged | Receipt `unavailable`/`failed` only | Task 15/16/20 test |
| Required Compose/browser/Godot/benchmark lane with a missing prerequisite | No green certification | Recorded `unexecuted` with prerequisite | Task 21/23 |

## Architecture and Decisions

1. **One new owned flag, one existing seam.** `formal_rules` is already declared
   in `simulation.v4_architecture` and requires `v4_capability_flags` on the
   accepted `runner-config-v56` keyset. V4-06 adds no runner schema, root field,
   or per-agent runner key; it adds an internal cognition mode and policy.
2. **A rule is a belief.** It is one owner's belief about a socially recognized
   constraint. It is not a world law, admission rule, permission, prohibition,
   court order, verdict, or enforceable statute.
3. **Physical and social constraints stay separate.** Physical impossibility is
   decided only by existing `WorldEngine` action rules. A formal rule can label
   an action prohibited, obligated, or permitted; it can never make a physically
   possible action impossible or a physically impossible action possible.
4. **The progression is monotone per owner rule.** `habit → expectation → norm →
   documented → recognized_enforcement`. Evidence can promote a stage; no
   evidence silently demotes it. Retirement is an explicit status, not a
   regression.
5. **Written representation is an anchor, not a truth claim.** A rule references
   an observed `artifact_id`, revision, genre, and optional repository. The
   ledger stores representation integrity as an owner belief; it never parses
   artifact content into objective law.
6. **Recognized authority is a belief threshold.** Office, institution concept,
   organization procedure, collective decision, or written record evidence can
   support recognition. Recognition is not a world permission and never changes
   admission.
7. **Expected sanctions are expectations.** Sanction kinds and severity are
   beliefs. Actual enforcement remains ordinary agent commands, speech, or
   relationship changes; no sanction engine dispatches anything.
8. **Exceptions are owner-local.** An exception can coexist with a prohibition
   and never upgrades into a global permission.
9. **Responses are owner declarations.** `follow`, `violate`, `challenge`,
   `reinterpret`, and `ignore` are bounded responses and claims. They are not
   objective compliance findings; silence is never a violation.
10. **Competing systems coexist.** Multiple `frs-` systems may cover the same
    scope or action with incompatible constraints. No precedence, majority,
    quorum, or consensus gate resolves them.
11. **No global rule registry.** Systems and rules are owner-local; detached
    analysis may mint `frule-` candidates after the run but never installs a
    global rule, canonical system, or objective jurisdiction.
12. **No executor or enforcer.** Formal-rule helpers may classify, compare,
    penalize existing plan candidates, and stamp existing `Talk`/`Tell`; they
    never return, construct, submit, or resolve an `AgentCommand`.
13. **Owner-only inputs.** The update reads one owner's observation and prepared
    owner ledgers only. Peer claims arrive through delivered communication or
    observed records, never through a peer ledger read.
14. **Speech is bounded and additive.** `fr_v1` relations travel inside existing
    `Talk`/`Tell`; `org_v1`, `org_op_v1`, `org_ca_v1`, and `collective_decision`
    frames are unchanged. No command, event, observer semantic, or free-text
    payload is added.
15. **Analysis never creates identity.** Formal-rule candidates are new
    analytical identities; they never create, split, merge, dissolve, or
    re-identify an organization or macro-society candidate.
16. **Three layers, three types.** Objective rows are counts of observed
    artifacts, repositories, and occurrences. Subjective rows use `frs-`/`frl-`
    ids. Analytical summaries use `frule-`. Leakage is a hard failure.
17. **A new snapshot, not an organization v4.** `formal-rule-snapshot-v1` is an
    independent canonical artifact. Organization snapshots v1/v2/v3 remain
    decodable and byte-verifiable; no organization schema changes.
18. **Metrics append only.** 148 → 151 with three new families; the first 148
    keep id, order, version, and value keys.
19. **Deterministic by construction.** Sorted ordering, content-addressed ids,
    canonical JSON digests, quantized floats, no `hash()`, no UUID, and no
    wall-clock domain values.
20. **Read-only surfaces.** Six GET routes under `/v1` require
    `SUBJECTIVE_DEBUG`; the Research UI renders server fields without deriving
    law, violation truth, or enforcement.
21. **Cursors bind to the publication digest.** Every paged formal-rule route
    binds run, publication, digest, filter, and offset through a signed cursor.
22. **Publication is opt-in and non-interfering.** A storage or composition
    failure changes only the receipt, never the scientific result.
23. **No automatic generalization.** The plan does not implement
    `legal_disputes`, `diplomacy`, `organized_conflict`, or any other V4 context.

### Context declaration

| Context | Flag | Authority | Owning packages | Prerequisites | Existing mechanism | Event strategy |
| --- | --- | --- | --- | --- | --- | --- |
| `formal_rules` | `formal_rules` (newly owned) | owner-scoped | `agents.cognition`, `simulation` | none | norms, conventions, institution concepts, offices, durable records, organization authority, collective decisions | reuse |

Supporting packages without authority: `analysis` (detached rows/metrics),
`experiments` (harvest/publication bridge), `persistence` (filesystem store),
`api` (read-only routes), `research_runner` (opt-in CLI producer), and the
Research UI client.

### Compatibility pins

Default runner/result `v4`/`v2`; latest feature runner `v55`; accepted runner adds
`v56` only; events `EVENT_SCHEMA_REPLAY_V22` (22); codec `v20`; commands 43;
observer semantic types 73; metric families **151 (V4-06 change)**; Alembic
`0017`; `/v1`; `observer-protocol-v1`; observer layout `observer-layout-v1`;
observer capabilities 4 advertised / 6 reserved; four reserved write pairs
(events 23-26 / codecs `v21`-`v24`); `prepare_parallel=False`; six GET
organization routes and six GET formal-rule routes; six cursor purposes per
context; snapshots `organization-snapshot-v1`/`v2`/`v3` plus
`formal-rule-snapshot-v1`; 14 V4 contexts / 12 flags / 2 owned flags.
`institutional_economy` and `multi_hop_testimony_tracking` remain unowned and fail
closed. `/version` is unchanged; `organization_rows` remains reserved.

## Phase Index

1. [Phase 1: Contract and Seam](phase-01-contract-and-seam.md) — Tasks 1-3
2. [Phase 2: Owner-Scoped Formal-Rule Beliefs](phase-02-rule-beliefs.md) — Tasks 4-8
3. [Phase 3: Detached Analysis, Competing Systems, and Metrics](phase-03-detached-analysis.md) — Tasks 9-12
4. [Phase 4: Formal-Rule Snapshot v1](phase-04-snapshot-v1.md) — Tasks 13-14
5. [Phase 5: Composition and Durable Publication](phase-05-composition-publication.md) — Tasks 15-16
6. [Phase 6: Read-Only API and Research UI](phase-06-read-only-surfaces.md) — Tasks 17-18
7. [Phase 7: Invariants, End-to-End Evidence, and Regression](phase-07-invariants-and-regression.md) — Tasks 19-21
8. [Phase 8: Documentation and Final Verification](phase-08-docs-and-verification.md) — Tasks 22-23

## Cross-Phase Dependencies

- All phases assume the completed V2/V3 norm, convention, institution, office,
  durable-record, V4-03/V4-04/V4-05 organization stacks are present; V4-06 does
  not rewrite them, but Tasks 19/21 must keep their suites green.
- Task 2 depends on Task 1: the ownership pin uses the frozen vocabulary and
  context seam.
- Task 3 depends on Task 2: the cognition mode and policy reference the owned
  flag.
- Task 4 depends on Task 3: records use the policy, ids, and limits.
- Task 5 depends on Task 4: `fr_v1` frames encode the record vocabulary.
- Task 6 depends on Tasks 4-5: the update consumes the frame parser and records.
- Task 7 depends on Task 6: responses, sanctions, exceptions, and competing
  systems consume the materialized ledger.
- Task 8 depends on Tasks 5-7: runtime carry and deliberation need the ledger,
  frame, and response policy.
- Task 9 depends on Task 8: harvest reads exported ledgers.
- Task 10 depends on Task 9: detection/identity consumes normalized rows.
- Task 11 depends on Tasks 9-10: layers consume rows and summaries.
- Task 12 depends on Tasks 10-11: the three families read the summary/layers.
- Task 13 depends on Tasks 10-12: the snapshot mirrors rows/counts and metric
  provenance.
- Task 14 depends on Task 13: paging selects typed snapshot records.
- Task 15 depends on Tasks 12 and 14: the composer needs analysis and ports.
- Task 16 depends on Tasks 13-15: the store serves snapshots and cursor pages,
  and the CLI producer calls the Task 15 composer.
- Task 17 depends on Task 16: the API reads the committed store.
- Task 18 depends on Task 17: the panel consumes the six routes and detail
  fields.
- Task 19 depends on Tasks 2-18: the suite asserts every authority claim.
- Task 20 depends on Tasks 6-18: the E2E uses the real update, command
  admission, artifact, publication, and surfaces.
- Task 21 depends on Tasks 19-20: regression runs after the invariant/E2E gates.
- Task 22 depends on Tasks 2-21: documentation describes verified surfaces.
- Task 23 depends on Tasks 21-22: final certification needs receipts and docs.

## Tasks

### Phase 1: Contract and Seam
- [x] Task 1: Freeze the formal-rule vocabulary, stages, and identity grammar ([details](phase-01-contract-and-seam.md#task-1-freeze-the-formal-rule-vocabulary-stages-and-identity-grammar))
- [x] Task 2: Own the `formal_rules` capability flag without a runner schema change ([details](phase-01-contract-and-seam.md#task-2-own-the-formal_rules-capability-flag-without-a-runner-schema-change)) (depends on 1)
- [x] Task 3: Add the cognition mode and policy seam ([details](phase-01-contract-and-seam.md#task-3-add-the-cognition-mode-and-policy-seam)) (depends on 2)

### Phase 2: Owner-Scoped Formal-Rule Beliefs
- [x] Task 4: Define formal-rule records, systems, versions, and ledger invariants ([details](phase-02-rule-beliefs.md#task-4-define-formal-rule-records-systems-versions-and-ledger-invariants)) (depends on 3)
- [x] Task 5: Add bounded `fr_v1` formal-rule speech frames ([details](phase-02-rule-beliefs.md#task-5-add-bounded-fr_v1-formal-rule-speech-frames)) (depends on 4)
- [x] Task 6: Collect evidence and materialize stages, systems, and versions ([details](phase-02-rule-beliefs.md#task-6-collect-evidence-and-materialize-stages-systems-and-versions)) (depends on 4, 5)
- [x] Task 7: Generate positions, responses, sanctions, exceptions, and competing systems ([details](phase-02-rule-beliefs.md#task-7-generate-positions-responses-sanctions-exceptions-and-competing-systems)) (depends on 6)
- [x] Task 8: Carry the ledger through cognition, runtime, checkpoints, and deliberation ([details](phase-02-rule-beliefs.md#task-8-carry-the-ledger-through-cognition-runtime-checkpoints-and-deliberation)) (depends on 5, 6, 7)

### Phase 3: Detached Analysis, Competing Systems, and Metrics
- [x] Task 9: Harvest owner formal-rule ledgers into detached rows and windows ([details](phase-03-detached-analysis.md#task-9-harvest-owner-formal-rule-ledgers-into-detached-rows-and-windows)) (depends on 8)
- [x] Task 10: Detect and summarize formal-rule systems without minting owner identity ([details](phase-03-detached-analysis.md#task-10-detect-and-summarize-formal-rule-systems-without-minting-owner-identity)) (depends on 9)
- [x] Task 11: Project formal rules into the three layers without leakage ([details](phase-03-detached-analysis.md#task-11-project-formal-rules-into-the-three-layers-without-leakage)) (depends on 9, 10)
- [x] Task 12: Add three metric families and raise the catalog to 151 ([details](phase-03-detached-analysis.md#task-12-add-three-metric-families-and-raise-the-catalog-to-151)) (depends on 10, 11)

### Phase 4: Formal-Rule Snapshot v1
- [x] Task 13: Define snapshot models, limits, and the canonical codec ([details](phase-04-snapshot-v1.md#task-13-define-snapshot-models-limits-and-the-canonical-codec)) (depends on 11, 12)
- [x] Task 14: Add paging, read ports, and cursor digest support ([details](phase-04-snapshot-v1.md#task-14-add-paging-read-ports-and-cursor-digest-support)) (depends on 13)

### Phase 5: Composition and Durable Publication
- [x] Task 15: Compose completed-run snapshots and receipts ([details](phase-05-composition-publication.md#task-15-compose-completed-run-snapshots-and-receipts)) (depends on 12, 14)
- [x] Task 16: Add the atomic filesystem store and CLI producer ([details](phase-05-composition-publication.md#task-16-add-the-atomic-filesystem-store-and-cli-producer)) (depends on 13, 14, 15)

### Phase 6: Read-Only API and Research UI
- [x] Task 17: Add six GET routes, schemas, settings, and app wiring ([details](phase-06-read-only-surfaces.md#task-17-add-six-get-routes-schemas-settings-and-app-wiring)) (depends on 16)
- [x] Task 18: Add the read-only Research UI formal-rules view ([details](phase-06-read-only-surfaces.md#task-18-add-the-read-only-research-ui-formal-rules-view)) (depends on 17)

### Phase 7: Invariants, End-to-End Evidence, and Regression
- [x] Task 19: Add the formal-rule boundary and determinism suite ([details](phase-07-invariants-and-regression.md#task-19-add-the-formal-rule-boundary-and-determinism-suite)) (depends on 2-18)
- [x] Task 20: Add the formal-rule end-to-end scenario ([details](phase-07-invariants-and-regression.md#task-20-add-the-formal-rule-end-to-end-scenario)) (depends on 6-18)
- [x] Task 21: Execute the full V1-V4 regression and qualification lanes ([details](phase-07-invariants-and-regression.md#task-21-execute-the-full-v1-v4-regression-and-qualification-lanes)) (depends on 19, 20)

### Phase 8: Documentation and Final Verification
- [x] Task 22: Execute the documentation checkpoint ([details](phase-08-docs-and-verification.md#task-22-execute-the-documentation-checkpoint)) (depends on 2-21)
- [x] Task 23: Perform final V4-06 verification ([details](phase-08-docs-and-verification.md#task-23-perform-final-v4-06-verification)) (depends on 21, 22)

## Verification Receipt (Tasks 21 and 23)

To be completed by Task 21 and audited by Task 23. Every required lane must be
recorded as exactly one of `executed_passed`, `executed_failed`, or
`unexecuted`. An `unexecuted` lane carries its missing prerequisite and blocks
certification; it is never a skip-pass.

| Lane | State | Evidence |
| --- | --- | --- |
| Python unit + architecture with coverage | `executed_passed` | `uv run pytest tests/unit tests/architecture -q` → 7,960 passed, 503.41s (second pass); coverage-enabled baseline 7,950 passed at 78% coverage in 34:17 |
| Focused V4-06 suite | `executed_passed` | `uv run pytest tests/unit/test_formal_rule_*.py tests/architecture/test_formal_rule_boundaries.py -q` → 221 passed, 5.60s (post-remediation, second pass) |
| V4/organization regression selection | `executed_passed` | `uv run pytest tests/unit -q -k "organization or v4 or formal_rule or metric_specification or runner_config_v56"` → 1,090 passed, 6,425 deselected, 14.85s; architecture selection → 144 passed, 301 deselected, 10.47s |
| Documentation parity | `executed_passed` | `uv run pytest tests/unit/test_formal_rule_docs.py -q` → 10 passed (second pass) |
| Ruff | `executed_passed` | `uv run ruff check src tests` → all checks passed |
| Mypy | `executed_passed` | `uv run mypy src tests` → no issues in 1,862 files |
| Import-linter | `executed_passed` | `uv run lint-imports` → 25 contracts kept, 0 broken |
| Integration (`-m "integration and not scale"`) | `executed_passed` | `PALIMPSEST_TEST_DATABASE_URL=...palimpsest_test_v406 uv run pytest -m "integration and not scale" -q` → 93 passed, 7,994 deselected, 29.37s against a disposable pgvector `pg17` database |
| Integration including scale | `executed_passed` | `PALIMPSEST_TEST_DATABASE_URL=...palimpsest_test_v406_scale uv run pytest -m "integration and scale" tests/integration -q` → 5 passed, 93 deselected in 2,830.42s (47:10), including the 100,000-tick generational lane |
| Docker Compose config | `executed_passed` | `docker compose config --quiet` → exit 0 |
| Compose/browser acceptance | `executed_passed` | `PALIMPSEST_API_IMAGE=palimpsest-api:v4accept PALIMPSEST_V3_ACCEPTANCE_REQUIRED=1 uv run pytest -m compose tests/compose/test_observer_browser.py tests/compose/test_research_ui_wiring.py tests/compose/test_stack.py -q` → 9 passed (1 + 4 + 4) in 23.90s / 64.80s / 102.72s |
| Godot 4.7.2 regression | `executed_passed` | `GODOT_BIN=.../Godot_v4.7.2-stable_linux.x86_64`; editor pass exit 0, `--headless --path clients/godot-observer --script res://tests/run_protocol.gd` exit 0, `godot_protocol_tests failed=0` |
| Benchmark/scale lane (disposable pgvector) | `executed_passed` | `PALIMPSEST_TEST_DATABASE_URL=...palimpsest_test_v406_bench uv run pytest -m "integration and scale" tests/benchmarks/ -q` → 18 passed, 3 deselected in 8,499.06s (2:21:39), including the 1,000-tick and 10,000-tick long-run baselines |
| Research UI tests | `executed_passed` | `npm run test` → 50 files, 256 tests passed |
| Research UI type/static checks | `executed_passed` | `npx svelte-check --tsconfig ./tsconfig.app.json` → 0 errors; `npx tsc -p tsconfig.node.json` → exit 0 |
| Research UI build | `executed_passed` | `npm run build` → built in 1.19s, `research_ui_build_ok file_count=5` |

Certification outcome: **certified**. Every required lane is
`executed_passed`: unit+architecture coverage (7,960 passed after the second
pass; 78% coverage baseline), focused V4-06 (221), V4/organization regression
(1,090 unit + 144 architecture), documentation parity (10), Ruff, mypy,
import-linter, integration (93),
integration including scale (5, including 100,000 ticks), Compose config,
Compose/browser (9), Godot 4.7.2 (failed=0), benchmark/scale (18), and the
Research UI tests/type/build lanes.

### Verification remediation (2026-11-03)

A verification pass found two task-level gaps and both are closed:

- Task 22 documentation checkpoint: added the V4-06 seam and 151-family pin to
  `.ai-factory/ARCHITECTURE.md`; corrected the owned/unowned flag statement and
  formal-rule settings in `docs/configuration.md`; marked `formal_rules` owned in
  `docs/v4-architecture.md`; added the pin statement and sibling links in
  `docs/architecture.md` and `docs/organizations.md`; expanded the six-route
  table and cursor errors in `docs/research-api.md`; added
  `tests/unit/test_formal_rule_docs.py`.
- Task 20 end-to-end scenario: added a real `Inscribe` record through
  `WorldEngine`, recognized-enforcement progression, a real `SimulationRunner`
  run asserting one owner ledger, snapshot publication followed by all six API
  route reads, collector-based metric assembly, and an injected publisher failure
  proving the runner result is unchanged. The focused suite reported 211
  passed immediately after this remediation; the final focused run (which adds
  the later formal-rule cases) reported 221 passed in the receipt table above.

All previously unexecuted lanes now pass. Integration ran against a disposable
pgvector `pg17` database (93 tests); integration including scale passed 5 tests
in 47:10, including the 100,000-tick generational lane; Compose/browser passed 9
checks with `palimpsest-api:v4accept` and Playwright chromium; the pinned Godot
4.7.2 editor/protocol pass reported `godot_protocol_tests failed=0`; and the
complete benchmark selection passed 18 tests in 2:21:39. A post-remediation full
unit+architecture coverage run passed 7,950 tests at 78% coverage in 34:17.

### Post-verification closure (2026-11-03)

No required lane remains unexecuted. Task 23 is checked, all 23 indexed tasks
have verified evidence, the pin checks are exact (151 families, 14 contexts, 12
flags, 2 owned, 4 reservations, replay-v22, no `v57`, no `0018`, no
`observer-protocol-v2` serving), `.ai-factory/ROADMAP.md` is unchanged, and no
branch or worktree was created by V4-06. The plan is certified complete.

### Second verification pass remediation (2026-11-03)

An independent verification pass found documentation and test-coverage gaps and
no functional defect. Both are closed:

- `docs/research-api.md` and `docs/v4-architecture.md` now state the current
  ownership split (two owned flags, ten unowned) instead of claiming every V4
  flag is unowned. `tests/unit/test_formal_rule_docs.py` pins both statements.
- `.ai-factory/ARCHITECTURE.md` restores the V4-05 seam's own catalog count
  (148) and keeps `148 -> 151` on V4-06; a docs test pins the attribution.
- Task 19 boundary coverage now proves no global registry or cross-owner store,
  settings never reads a ledger, app wiring imports no analysis/experiments or
  production bridge, and no new event, command, observer semantic, write pair,
  or migration exists. The determinism suite proves shuffled `fr_v1` deliveries
  produce an identical ledger, and the previously vacuous shuffled-evidence test
  now compares two real permutations.
- Task 16/17 coverage now proves the receipt is written next to the artifacts, a
  receipt-write failure is ignored, success-path publication leaves the runner
  result unchanged, and oversized responses fail with 400
  `formal_rule_size_limit`.
- The recorded architecture-selection count is corrected to the reproducible
  value (144 passed / 301 deselected), and the `runner-config-v57` grep steps
  now state that only pinning negative assertions may mention the identifier.

## Commit Plan

Proposed implementation checkpoints; no commit is made by planning.

1. After Tasks 1-3: `feat(v4): own the formal-rules capability contract`
2. After Tasks 4-8: `feat(v4): form owner-scoped formal rules`
3. After Tasks 9-12: `feat(v4): analyze formal rules and responses`
4. After Tasks 13-16: `feat(v4): publish formal-rule-snapshot-v1`
5. After Tasks 17-18: `feat(v4): serve read-only formal rules`
6. After Tasks 19-23: `test(v4): enforce formal-rule invariants`

## Blocking Conditions and Non-Goals

- Adding `runner-config-v57`, a new V4 flag, a new runner root field, or a
  per-agent runner mode to make this plan work is a blocking scope violation.
  Stop and re-plan.
- Creating an objective Law, Statute, LegalCode, Court, Judge, Police, Government,
  State, Jurisdiction, RuleEngine, SanctionEngine, PolicyEngine, or global rule
  registry is forbidden.
- Letting `WorldEngine`, perception, admission, stop selectors, memory, prompts,
  or observer semantics read a formal-rule ledger is forbidden.
- Letting a formal-rule helper return, construct, submit, or resolve an
  `AgentCommand`, move a resource, or execute a physical action is forbidden.
- Treating a rule belief as a physical law, admission gate, permission, or
  prohibition is forbidden.
- Inferring violation from silence or from an unobserved act is forbidden.
- Adding an objective `law_id`, `jurisdiction`, `owner_id`/`ownership`, or
  `enforced_by_world` field to items, resources, structures, artifacts,
  repositories, or world state is forbidden.
- Adding a new event, command, observer semantic type, write pair, artifact kind,
  durable-record genre, `/v2` route, `observer-protocol-v2` serving, or SQL
  migration is forbidden.
- Rewriting the V2 norm ledger, V3 convention/institution/office/durable-record
  contracts, or the V4-03/V4-04/V4-05 organization contracts is forbidden;
  formal rules are additive.
- Weakening an existing pin or assertion (catalog counts, Alembic `0017`, replay
  v22, codec v20, command count, observer semantic count, context count) is
  forbidden. The only intentional pin changes are 148 → 151 metric families,
  the addition of six formal-rule routes alongside the six organization routes,
  and the owned-flag set 1 → 2.
- Claiming prevalence, emergence probability, predictive power, capacity,
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
- Do not implement any other V4 context (`legal_disputes`, `diplomacy`,
  `organized_conflict`, `infrastructure_networks`, `supply_chains`,
  `markets_credit`, `science`, `epidemics`, `ecological_feedback`, `disasters`,
  `societal_resilience`, `macro_society_identity`, or a second `organizations`
  extension) in this plan.

## Definition of Done

- All 23 indexed tasks have verified completion evidence; only this index holds
  task progress checkboxes.
- `formal_rules` is the second owned V4 flag on `runner-config-v56`; no `v57`,
  new flag, root field, or per-agent runner key exists.
- The context registry validates at 14 contexts, 12 flags, and
  `v4-context-map-v2`; the analysis-only set and four reservations are unchanged.
- A formal rule is an owner belief with scope, proponents, recognized authority,
  written representation, expected sanction, exceptions, historical versions,
  and status; no objective law object or global registry exists.
- The progression `habit → expectation → norm → documented →
  recognized_enforcement` exists and is monotone within one owner rule.
- Agents can follow, violate, challenge, reinterpret, or ignore a rule; these are
  bounded responses or claims, never objective compliance findings.
- Competing rule systems coexist without precedence, majority, quorum, or
  consensus resolution.
- `WorldEngine` never reads a formal-rule ledger; a socially prohibited but
  physically possible command is still admitted, and a physically impossible
  command is still rejected by the existing rules.
- No formal-rule helper constructs, submits, or executes a command; enforcement
  and sanctions remain ordinary agent actions.
- Written representation references existing observed durable records and
  repositories only; no new artifact kind, genre, or objective ownership field is
  added.
- Owner-local `frs-`/`frl-`/`frv-`/`fre-`/`frp-`/`frr-`/`frx-` ids carry
  provenance; publication exposes deterministic `frule-`/`frul-`/`fruv-`/
  `frule-edge-` records without owner-local ids.
- Detached analysis never creates an objective rule or changes an organization
  candidate; objective counts, owner claims, and analytical summaries remain
  separate.
- The metric catalog is exactly 151 with three appended families; the first 148
  are unchanged, and real completed-run assembly emits all three documents.
- `formal-rule-snapshot-v1` is canonical, bounded, immutable after publication,
  and organization snapshots v1/v2/v3 remain decodable and byte-verifiable.
- Six GET-only `/v1` formal-rule routes require `SUBJECTIVE_DEBUG`, have an
  explicit `formal_rule_disabled` state, and are consumed by a read-only
  Research UI view.
- Cursor reuse works on every paged formal-rule route; changed
  filter/run/publication/digest fails with 400 and expiry with 410.
- The boundary suite proves owner-only authority, absence of magic actors, law
  engines, sanction engines, global registries, objective jurisdictions, command
  construction, and world-ledger reads; no new
  commands/events/migrations/artifact kinds; unchanged observer/migration pins.
- The full V1-V4 regression lanes and static gates execute and pass; any
  unexecuted required lane is reported with its blocker and is not certified.
- Documentation states what a formal rule controls (a belief), what it never
  controls (objective action), how physical impossibility differs from social
  prohibition, how competing systems and versions work, how responses and
  sanctions are attributed, and every count matches the code.
