<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-07 Structured Dispute Resolution

Mode: ultra
Branch: main
Created: 2026-11-03
Plan identifier: `v4-07-dispute-resolution`
Status: implemented; verification recorded; documentation and roadmap findings addressed; certification withheld (unexecuted qualification lanes)

## Original Request

v4-07 disputes and legal reasoning

Naming requirement:

Use `v4-07-dispute-resolution`.

Implement structured social disputes.

Examples:

- contested debt

- ownership claim

- contract interpretation

- injury

- broken promise

- resource appropriation

Represent claims made by parties separately.

Agents may sincerely disagree because memories differ.

Support:

claim
counterclaim
testimony
evidence references
rule references
mediation
proposed resolution
accepted/rejected resolution

Do not implement an objective justice oracle.

Research infrastructure knows objective history but agents do not.

Integrate with existing mediation and institutional roles.

## Settings

- Testing: yes; full strategy. Unit, architecture, determinism, integration,
  Compose/browser, Godot regression, Research UI, benchmark regression, and
  static gates, with coverage enabled for Python lanes.
- Logging: verbose, metadata-only. Bounded DEBUG flow/counts, INFO milestones,
  WARN incomplete evidence/truncation, ERROR safe codes. `PALIMPSEST_LOG_LEVEL`
  controls operational verbosity. No claim text, subject tokens, party sets,
  evidence ids, rule ids, mediation ids, resolution terms, private content,
  payload surrogates, prompts, credentials, tokens, DSNs, memories, embeddings,
  utterance bodies, labels, or artifact payloads.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 23.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints are suggestions, not authorization to
  commit during planning.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-07-dispute-resolution`; the ultra bundle directory
  is `.ai-factory/plans/v4-07-dispute-resolution/`, phase files use
  `phase-NN-<slug>.md`, and `index.md` is the canonical entrypoint.
- Research source: `.ai-factory/RESEARCH.md` and `.ai-factory/research/` do not
  exist; no external research conclusions are invented.
- Execution: plan only. No implementation, commit, roadmap edit, or branch
  creation occurs in this invocation.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"
Rationale: V4-07 owns the already-declared owner-scoped `legal_disputes` V4
context on the accepted `runner-config-v56` seam and implements structured
claims, testimony, evidence, rule references, mediation links, and proposed or
declared resolutions without creating an objective justice oracle. This plan
does not edit or close the roadmap; `$aif-roadmap` must register V4-07 in M8.

## Requirements Reconciliation

Authority: the Original Request defines scope; `.ai-factory/ARCHITECTURE.md`
("Key Principles", "Capability ownership", "Important V3 seams", "Versioned
Extension Contract", V4-01 through V4-06 seams) and `.ai-factory/RULES.md`
constrain every edit; `.ai-factory/DESCRIPTION.md` and `.ai-factory/ROADMAP.md`
describe current state; completed V3 mediation, structured-commitment,
subjective-value, institution, office, organization, operation, collective
agency, formal-rule, durable-record, and archive code plus the
`tests/architecture/test_*organization*`, `test_formal_rule_boundaries`,
`test_v4_*`, and `test_*mediation*` suites govern compatibility. V4-07 owns
exactly one already-declared V4 capability flag, `legal_disputes`; it may not
create a court, judge, jurisdiction, verdict, binding settlement, justice
engine, or global dispute registry.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-07 owns the declared `legal_disputes` context; no other V4 flag, `runner-config-v57`, new root field, or per-agent runner key is added | Original Request "disputes and legal reasoning"; `.ai-factory/ARCHITECTURE.md` "Capability ownership"; `src/simulation/v4_architecture.py` 136-149; `src/simulation/runner_models.py` 305-325, 1114-1163 | Task 2/3 tests; Task 20 pins; Task 24 `v57` absence |
| The user-requested `legal_disputes` work may land before `infrastructure_networks`; the declared prerequisite is `formal_rules`, which is implemented, and roadmap ordering is a priority rather than a technical dependency | `.ai-factory/ROADMAP.md` "Next plans" under M8; `src/simulation/v4_architecture.py` 136-149 | Task 2 test; Task 24 audit |
| The declared prerequisite `formal_rules` is implemented; `legal_disputes` may run with or without the `formal_rules` flag, and without it rule references remain `orphaned` | `src/simulation/v4_architecture.py` 136-149; `src/agents/cognition/formal_rules.py` 356-404, 1289-1395 | Task 2/7/20 tests |
| A dispute is an owner-scoped belief about claims, never a shared case registry or objective truth | Original Request; `.ai-factory/ARCHITECTURE.md` Key Principle 1 and "Memory, testimony, and subjective concepts" | Task 4/7/20 tests |
| Each claim and counterclaim is attributed to a verified claimant; opposing claims coexist and are never reconciled into one truth | Original Request "Represent claims made by parties separately"; `src/agents/cognition/mediation.py` 158-205, 2280-2335 | Task 4/6/11/21 tests |
| Agents may sincerely disagree because remembered evidence differs; separate memory-trace references are retained without ground-truth correction | Original Request "Agents may sincerely disagree because memories differ"; `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts"; `src/memory/` recall contracts | Task 6/7/12/21 tests |
| Claims support the six requested kinds: contested debt, ownership claim, contract interpretation, injury, broken promise, resource appropriation | Original Request examples; `src/agents/cognition/structured_commitments.py` commitment kinds; `src/world/events.py` 586-827; `src/agents/cognition/subjective_value.py` exchange views | Task 1/6/21 tests |
| Testimony is an attributed account, not truth; direct and communicated testimony are distinct and shared roots are not independent corroboration | `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts"; `src/agents/cognition/mediation.py` 2280-2335; `src/world/communications.py` | Task 5/6/10/12 tests |
| Evidence references are typed owner-visible anchors (opaque event correlation, memory trace, artifact, record, repository entry, commitment, valuation, mediation/rule/office/institution/organization record); no `WorldEvent`, `WorldState`, or event store is carried | `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime", "Memory, testimony, and subjective concepts"; `src/world/observations.py` 232-281 | Task 4/6/20 tests |
| Rule references point to the owner's own formal-rule ledger (`frs-`/`frl-`/`frv-`); a missing or mismatched rule is `orphaned` or `version_mismatch`, never invented | Original Request "rule references"; `src/agents/cognition/formal_rules.py` 356-404, 1289-1395; `src/agents/cognition/formal_rule_communication.py` 54-75 | Task 7/21 tests |
| Mediation integration reads only the owner's own `MediationLedger`; cases, recommendations, responses, and outcomes are linked as beliefs, never as a binding decision | Original Request "mediation"; `src/agents/cognition/mediation.py` 74, 1373-1398, 3068; `src/agents/cognition/mediation_communication.py` 49 | Task 7/8/21 tests |
| Institutional-role integration cites existing office, institution, organization, collective-decision, procedure, or record beliefs as authority references; no new role, judge, or court exists | Original Request "institutional roles"; `src/agents/cognition/offices.py` `OfficeFunction.CONFLICT_MEDIATION`; `src/agents/cognition/institution_concepts.py`; `src/agents/cognition/organization_concepts.py` | Task 7/21 tests |
| Resolutions are proposals; acceptance and rejection are per-party declarations, never binding findings; `apparently_accepted` requires every named party's active declaration and still binds nobody; acceptance requires a proposal observed in a prior committed tick | Original Request "proposed resolution / accepted/rejected resolution"; `src/agents/cognition/mediation.py` 158-205; `src/agents/cognition/loop.py` 2716-2760, 5221-5274; `.ai-factory/ARCHITECTURE.md` "Important V3 seams" V3-32 | Task 8/11/21 tests |
| No helper constructs, submits, resolves, or executes an `AgentCommand`; a linked mediation undertaking may only reuse `compile_mediation_undertaking`, and every physical effect remains an ordinary admitted command | Original Request "Do not implement an objective justice oracle"; `src/agents/cognition/mediation_actions.py` 75-125; `src/simulation/actions.py` | Task 8/20/21 tests |
| `WorldEngine`, perception, admission, stop selectors, memory, prompts, and observer semantics never read a dispute ledger; a socially disputed but physically possible command is still admitted | Original Request "Do not implement an objective justice oracle"; `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime" | Task 9/20/21 tests |
| Detached analysis may join owner rows with objective committed history for researcher-only alignment, but that alignment never reaches cognition, prompts, memory, world state, or stop selectors | Original Request "Research infrastructure knows objective history but agents do not"; `.ai-factory/ARCHITECTURE.md` Key Principle 1, "analysis is read-only" | Task 10/12/13/20 tests |
| Objective counts, owner claims, and analytical summaries remain three distinct types with hard leakage checks | `.ai-factory/ARCHITECTURE.md` Key Principle 1; `src/analysis/formal_rule_layers.py` 34-81, 226-303 | Task 12/20 tests |
| The metric catalog grows from 151 to 154 by appending `dispute_claim_structure@1`, `dispute_testimony_independence@1`, and `dispute_resolution_alignment@1`; the first 151 families keep id, order, version, and value keys | `src/analysis/specifications.py` 52-53, 226-228, 6973-6984 | Task 13/20/24 pin checks |
| `dispute-resolution-snapshot-v1` is a new independent artifact; organization v1/v2/v3 and formal-rule v1 snapshots remain byte-verifiable and unchanged | `.ai-factory/ARCHITECTURE.md` "Use accepted-set and exact-key-set schema evolution"; `src/simulation/formal_rule_codec.py`; `src/simulation/organization_codec.py` | Task 14/20/24 snapshot tests |
| Access is six GET-only `/v1` dispute routes requiring `SUBJECTIVE_DEBUG`; the six organization and six formal-rule routes keep their paths | `docs/research-api.md`; `src/api/routes/formal_rule.py` 43, 238-544; `src/api/routes/organization.py` | Task 18/20 route tests; Task 21 API reads |
| Cursors bind to the publication digest and query fingerprint; changed run/filter/publication/digest fails with 400 and expiry with 410 | `src/api/formal_rule_cursor.py` 26, 76-135; `src/simulation/formal_rule_ports.py` 37-232 | Task 15/18/21 cursor tests |
| Publication is opt-in, post-completion, atomic, quota-bounded, and isolated from scientific status; new CLI flags and env root follow the formal-rule precedent | `src/experiments/formal_rule_publication.py`; `src/research_runner/formal_rule_composition.py` 65-135 | Task 16/17/21 receipts and failure-isolation tests |
| No SQL migration, new event, command, observer semantic type, write pair, `/v2` route, or `observer-protocol-v2` is added; Alembic stays `0017`, events 22, codec v20, commands 43, semantics 73 | `.ai-factory/ARCHITECTURE.md` requirements 4-6; `src/simulation/versioning.py` 77-90 | Task 20/24 pins |
| Dispute rows flow through `MetricComputationInputs`, `experiments.collectors`, and `analysis.metric_service`; the new families are emitted by real completed-run assembly | `.ai-factory/ARCHITECTURE.md` "analysis is read-only"; `src/analysis/metric_service.py` 218-327, 1561-1625; `src/experiments/collectors.py` 817-826 | Task 10/13 tests; Task 21 metric assembly |
| The carried ledger reaches `Perspective` through `build_perspective` and `SimulationRunnerResult` validates ordered ledger sequences | `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime"; `src/simulation/perception.py` 143, 354; `src/simulation/runner_models.py` 6380, 6683-6695 | Task 9 tests; Task 20 carry scan |
| Required lanes must execute; a missing prerequisite is reported `unexecuted` with a prerequisite, never as a skip-pass | Plan Settings "Testing: yes; full strategy"; `docs/development.md`; `tests/compose/acceptance.py` | Task 22 three-state receipt; Task 24 audit |
| The roadmap is owned by `$aif-roadmap` and is not edited here | `.ai-factory/ARCHITECTURE.md` requirement 7 | Task 23/24 `git status` |

### Supported combinations and availability transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| Default runner config, all V4 flags off | V4-06-equivalent behavior | No dispute ledger, policy, metric, publication, or route data | Task 3/9/21 flags-off tests |
| `legal_disputes` enabled on v4 or v55 | Unchanged config | `v4_capability_requires_v56` before construction | Task 2 test |
| `legal_disputes` enabled on v56 without `formal_rules` | Valid run | Dispute ledger works; every rule reference is `orphaned`; no rule invented | Task 2/7 test |
| `legal_disputes` enabled on v56 with `formal_rules` | Valid run | Rule references resolve against the owner's formal-rule ledger | Task 7/21 test |
| Flag on v56, no dispute ledger/channel | Valid run | Dispute metrics `ABSENT`; no fabricated case | Task 6/13 tests |
| Flag on v56, enabled ledger with zero cases | Valid run | Metrics `PRESENT` with zero counts and explicit coverage; not fabricated | Task 13 test |
| Same-tick proposal and acceptance | Prior-tick proposal only | `dispute_resolution_requires_prior_tick`; acceptance requires a proposal observed in a prior committed tick | Task 8/21 tests |
| Owner asserts a claim through existing `Talk`/`Tell` | Attributed claim | `dsc-`/`dcl-` records; case status `open`; no world change | Task 5/6/21 tests |
| Counterparty asserts a counterclaim | Attributed counterclaim | Separate `dcl-` record with `role=counterclaim`; both claims retained; case `contested` | Task 5/6/11/21 tests |
| Two owners remember one event differently | Two evidence sets | Separate evidence/memory refs; no reconciliation; analysis reports divergence | Task 6/7/12/21 tests |
| Direct testimony from a first-hand witness | Direct testimony | `dts-` record with `channel=direct`, `independently_evidenced` only when the root is distinct | Task 5/6/12 tests |
| Retold testimony sharing a root | Communicated testimony | `channel=communicated`; shared root is not independent corroboration | Task 5/6/12 tests |
| Evidence reference to an observed occurrence or communication | Typed evidence | Opaque event correlation retained; no `WorldEvent` object | Task 4/6/20 tests |
| Evidence reference to a memory trace or reconstructed memory | Typed evidence | Owner-local memory id retained; no ground-truth correction | Task 4/6/21 tests |
| Rule reference found in the owner formal-rule ledger | Resolved rule reference | `status=resolved`; applicability/interpretation beliefs retained | Task 7/21 tests |
| Rule reference absent from the owner formal-rule ledger | Orphaned reference | `status=orphaned`; no rule minted; claim still stands | Task 7 test |
| Rule reference with a different version | Version mismatch | `status=version_mismatch`; no silent upgrade | Task 7 test |
| Mediation case linked to a dispute | Linked mediation reference | `dmr-` record; recommendation/response/outcome refs retained | Task 7/21 tests |
| Mediator recommendation becomes a dispute resolution | Proposed resolution | `drs-` record with `source=mediator`; not binding | Task 7/8/21 tests |
| Party accepts a proposed resolution | Per-party acceptance | `drp-` response `accept`; resolution `partially_accepted` or `apparently_accepted` | Task 8/11 tests |
| Party rejects a proposed resolution | Per-party rejection | `drp-` response `reject`; resolution `contested`; no enforcement | Task 8/11 tests |
| Every named party actively accepts | Apparently accepted | `apparently_accepted`; still not binding; no forced transfer | Task 8/21 tests |
| A speaker claims another party's acceptance | Attributed declaration | Actor remains the verified speaker; no forged party acceptance | Task 5/8/20 tests |
| Mediation recommendation exactly supports a `Give` and the owner independently selects it | Ordinary command | `compile_dispute_undertaking` delegates to `compile_mediation_undertaking`; no new command path | Task 8/21 tests |
| Socially disputed but physically possible command | Dispute belief retained | Ordinary command admitted; dispute ledger never reaches admission | Task 20/21 tests |
| Physically impossible command | Existing admission rejection | Unchanged error; no dispute attribution | Task 20 test |
| Objective history supports a claim | Researcher-only alignment | Analysis value key increments; agent ledger and prompt unchanged | Task 10/12/13/21 tests |
| Objective history is inconsistent with a claim | Researcher-only alignment | `inconsistent` count increments; agent ledger unchanged; no verdict | Task 10/12/13/20 tests |
| Candidate exceeds 64 claims or 32 resolutions | Deterministic truncation | `dispute_truncated`; no silent drop | Task 14/16 tests |
| Snapshot exceeds 4096 cases / 8192 claims / 4 MiB | No publication | `dispute_size_limit` | Task 14/16 tests |
| Duplicate publication id with different bytes | Existing publication untouched | `dispute_publication_exists` | Task 17 test |
| `PALIMPSEST_DISPUTE_ROOT` unset | API state unset | 503 `dispute_disabled`; CLI receipt `disabled` | Task 18/21 tests |
| Cursor reused with same filter/run/publication/digest | Same page | 200; digest matches | Task 15/18 test |
| Cursor reused with changed filter/run/publication/digest | No page served | 400 `dispute_cursor_invalid`; expired 410 | Task 15/18 test |
| Run incomplete or publication failed | Scientific result unchanged | Receipt `unavailable`/`failed` only | Task 16/17/21 test |
| Required Compose/browser/Godot/benchmark lane with a missing prerequisite | No green certification | Recorded `unexecuted` with prerequisite | Task 22/24 |

## Architecture and Decisions

1. **One newly owned flag, one existing seam.** `legal_disputes` is already
   declared in `simulation.v4_architecture` and requires
   `v4_capability_flags` on the accepted `runner-config-v56` keyset. V4-07 adds
   no runner schema, root field, or per-agent runner key; it adds an internal
   cognition mode and policy.
2. **A dispute is an owner belief.** It is one owner's view of attributed
   claims, testimony, evidence, rule interpretations, mediation links, and
   proposed or declared resolutions. It is not a shared case file, court record,
   verdict, judgment, or objective truth.
3. **Claims stay attributed and separate.** Every `dcl-` claim names its
   verified claimant and the party it is about. Opposing claims coexist. The
   ledger never merges them into a neutral proposition, winner, or liability
   finding.
4. **Sincere disagreement is legal.** Two owners may hold incompatible claims
   because their remembered evidence differs. The ledger retains both memory
   references and does not correct either against objective history.
5. **Evidence is a typed reference, not a truth claim.** Evidence kinds are
   closed. Observed occurrences/communications carry only opaque `EventId`
   correlation. Memory, artifact, record, repository, commitment, valuation,
   mediation, rule, office, institution, and organization references are
   owner-visible anchors, not payload copies.
6. **Testimony is not corroboration by repetition.** Direct and communicated
   testimony are distinct. Shared roots are not independent. A speaker cannot
   attribute a claim or acceptance to another party; the actor is always the
   verified speaker.
7. **Rules are referenced beliefs.** Rule references point to the owner's own
   formal-rule ledger. Missing or mismatched rules remain `orphaned` or
   `version_mismatch`. A rule reference never grants permission, prohibition, or
   enforcement.
8. **Institutional roles are existing beliefs.** Office, institution,
   organization, collective-decision, procedure, and written-record references
   are authority beliefs. The existing `conflict_mediation` office function and
   `appraise_mediation_authority` provide appraisal evidence; no judge, court,
   or jurisdiction object is created.
9. **Mediation is linked, not reimplemented.** The dispute ledger reads only the
   owner's mediation ledger. Recommendations and responses become dispute
   resolutions and responses. The only supported undertaking path reuses
   `compile_mediation_undertaking`; no second command compiler exists.
10. **Resolutions are proposals.** `proposed`, `partially_accepted`,
    `apparently_accepted`, `contested`, `withdrawn`, `expired`, and `superseded`
    describe owner knowledge. `apparently_accepted` requires every named party's
    active declaration and still binds nobody.
11. **No objective justice oracle.** No component returns a verdict, guilt,
    liability, damages, ownership truth, or binding settlement. `WorldEngine`
    never reads a dispute ledger. A socially disputed but physically possible
    command is still admitted.
12. **Research-only objective alignment.** Detached analysis may join owner rows
    with committed objective events to classify claim support as `supported`,
    `unresolved`, `inconsistent`, or `not_applicable`. That classification never
    reaches cognition, prompts, memory, world state, observer semantics, or stop
    selectors.
13. **No global dispute registry.** Owner-local `dsc-`/`dcl-`/`dts-`/`dev-`/
    `drf-`/`dmr-`/`dar-`/`drs-`/`drp-` ids stay private. Detached analysis may
    mint `disp-` candidates after the run, but it never creates a shared case or
    authoritative dispute identity.
14. **Analysis never creates identity for another context.** Dispute candidates
    never create, split, merge, dissolve, or re-identify a formal-rule,
    organization, macro-society, office, institution, or mediation candidate.
15. **Three layers, three types.** Objective rows are aggregate counts of
    observed events, transfers, harm, records, and communications. Subjective
    rows use owner-local ids. Analytical summaries use `disp-`. Leakage is a
    hard failure.
16. **A new snapshot, not an organization or formal-rule version.**
    `dispute-resolution-snapshot-v1` is independent and canonical. Organization
    snapshots v1/v2/v3 and `formal-rule-snapshot-v1` remain decodable and
    byte-verifiable.
17. **Metrics append only.** 151 → 154 with three new families. The first 151
    keep id, order, version, and value keys.
18. **Deterministic by construction.** Sorted ordering, content-addressed ids,
    canonical JSON digests, quantized floats, no `hash()`, no UUID, and no
    wall-clock domain values.
19. **Read-only surfaces.** Six GET routes under `/v1` require
    `SUBJECTIVE_DEBUG`; the Research UI renders server fields without deriving
    truth, guilt, liability, or a winning party.
20. **Cursors bind to the publication digest.** Every paged dispute route binds
    run, publication, digest, filter, and offset through a signed cursor.
21. **Publication is opt-in and non-interfering.** A storage or composition
    failure changes only the receipt, never the scientific result.
22. **No automatic generalization.** The plan does not implement `diplomacy`,
    `organized_conflict`, `science`, or any other V4 context.
23. **Scope ordering.** The user requested `legal_disputes`; its declared
    prerequisite is `formal_rules`, which is implemented. `infrastructure_networks`
    remains unowned and is not a prerequisite. The roadmap's preferred order is a
    priority, not a technical dependency.

### Context declaration

| Context | Flag | Authority | Owning packages | Prerequisites | Existing mechanism | Event strategy |
| --- | --- | --- | --- | --- | --- | --- |
| `legal_disputes` | `legal_disputes` (newly owned) | owner-scoped | `agents.cognition`, `simulation` | `formal_rules` | mediation, structured commitments, subjective value, offices, institutions, organizations, formal rules | reuse |

Supporting packages without authority: `analysis` (detached rows/metrics),
`experiments` (harvest/publication bridge), `persistence` (filesystem store),
`api` (read-only routes), `research_runner` (opt-in CLI producer), and the
Research UI client.

### Compatibility pins

Default runner/result `v4`/`v2`; latest feature runner `v55`; accepted runner adds
`v56` only; events `EVENT_SCHEMA_REPLAY_V22` (22); codec `v20`; commands 43;
observer semantic types 73; metric families **154 (V4-07 change)**; Alembic
`0017`; `/v1`; `observer-protocol-v1`; observer layout `observer-layout-v1`;
observer capabilities 4 advertised / 6 reserved; four reserved write pairs
(events 23-26 / codecs `v21`-`v24`); `prepare_parallel=False`; six GET
organization routes, six GET formal-rule routes, and six GET dispute routes;
six cursor purposes per context; snapshots `organization-snapshot-v1`/`v2`/`v3`,
`formal-rule-snapshot-v1`, and `dispute-resolution-snapshot-v1`; 14 V4 contexts
/ 12 flags / **3 owned flags**. `institutional_economy` and
`multi_hop_testimony_tracking` remain unowned and fail closed. `/version` is
unchanged; `organization_rows` remains reserved.

## Phase Index

1. [Phase 1: Contract and Seam](phase-01-contract-and-seam.md) — Tasks 1-3
2. [Phase 2: Owner-Scoped Dispute Beliefs](phase-02-dispute-beliefs.md) — Tasks 4-9
3. [Phase 3: Detached Analysis, Candidates, and Metrics](phase-03-detached-analysis.md) — Tasks 10-13
4. [Phase 4: Dispute-Resolution Snapshot v1](phase-04-snapshot-v1.md) — Tasks 14-15
5. [Phase 5: Composition and Durable Publication](phase-05-composition-publication.md) — Tasks 16-17
6. [Phase 6: Read-Only API and Research UI](phase-06-read-only-surfaces.md) — Tasks 18-19
7. [Phase 7: Invariants, End-to-End Evidence, and Regression](phase-07-invariants-and-regression.md) — Tasks 20-22
8. [Phase 8: Documentation and Final Verification](phase-08-docs-and-verification.md) — Tasks 23-24

## Cross-Phase Dependencies

- All phases assume the completed V2/V3 mediation, structured-commitment,
  subjective-value, institution, office, organization, operation, collective
  agency, formal-rule, durable-record, and archive stacks are present; V4-07
  does not rewrite them, but Tasks 20/22 must keep their suites green.
- Task 2 depends on Task 1: the ownership pin uses the frozen vocabulary and
  context seam.
- Task 3 depends on Task 2: the cognition mode and policy reference the owned
  flag.
- Task 4 depends on Task 3: records use the policy, ids, and limits.
- Task 5 depends on Task 4: `dsp_v1` frames encode the record vocabulary.
- Task 6 depends on Tasks 4-5: the update consumes the frame parser and records.
- Task 7 depends on Task 6: rule, authority, and mediation references consume
  materialized cases.
- Task 8 depends on Tasks 6-7: resolutions consume cases, references, and
  mediation links.
- Task 9 depends on Tasks 4-8: runtime carry and deliberation need records,
  frames, references, and resolution policy.
- Task 10 depends on Task 9: harvest reads exported ledgers and objective events.
- Task 11 depends on Task 10: detection/identity consumes normalized rows.
- Task 12 depends on Tasks 10-11: layers consume rows and summaries.
- Task 13 depends on Tasks 10-12: the three families read summary/layers.
- Task 14 depends on Tasks 10-13: the snapshot mirrors rows/counts and metric
  provenance.
- Task 15 depends on Task 14: paging selects typed snapshot records.
- Task 16 depends on Tasks 13 and 15: the composer needs analysis and ports.
- Task 17 depends on Tasks 14-16: the store serves snapshots and cursor pages,
  and the CLI producer calls the Task 16 composer.
- Task 18 depends on Task 17: the API reads the committed store.
- Task 19 depends on Task 18: the panel consumes the six routes and detail
  fields.
- Task 20 depends on Tasks 2-19: the suite asserts every authority claim.
- Task 21 depends on Tasks 6-19: the E2E uses the real update, command
  admission, mediation, publication, and surfaces.
- Task 22 depends on Tasks 20-21: regression runs after the invariant/E2E gates.
- Task 23 depends on Tasks 2-22: documentation describes verified surfaces.
- Task 24 depends on Tasks 22-23: final certification needs receipts and docs.

## Tasks

### Phase 1: Contract and Seam
- [x] Task 1: Freeze the dispute vocabulary and identity grammar ([details](phase-01-contract-and-seam.md#task-1-freeze-the-dispute-vocabulary-and-identity-grammar))
- [x] Task 2: Own the legal_disputes capability flag ([details](phase-01-contract-and-seam.md#task-2-own-the-legal_disputes-capability-flag)) (depends on 1)
- [x] Task 3: Add the cognition mode and policy seam ([details](phase-01-contract-and-seam.md#task-3-add-the-cognition-mode-and-policy-seam)) (depends on 2)

### Phase 2: Owner-Scoped Dispute Beliefs
- [x] Task 4: Define dispute records and ledger invariants ([details](phase-02-dispute-beliefs.md#task-4-define-dispute-records-and-ledger-invariants)) (depends on 3)
- [x] Task 5: Add bounded dsp_v1 dispute speech frames ([details](phase-02-dispute-beliefs.md#task-5-add-bounded-dsp_v1-dispute-speech-frames)) (depends on 4)
- [x] Task 6: Collect claims, testimony, and evidence ([details](phase-02-dispute-beliefs.md#task-6-collect-claims-testimony-and-evidence)) (depends on 4, 5)
- [x] Task 7: Derive rule, authority, and mediation references ([details](phase-02-dispute-beliefs.md#task-7-derive-rule-authority-and-mediation-references)) (depends on 6)
- [x] Task 8: Propose and respond to resolutions ([details](phase-02-dispute-beliefs.md#task-8-propose-and-respond-to-resolutions)) (depends on 6, 7)
- [x] Task 9: Carry the ledger through cognition and runtime ([details](phase-02-dispute-beliefs.md#task-9-carry-the-ledger-through-cognition-and-runtime)) (depends on 4-8)

### Phase 3: Detached Analysis, Candidates, and Metrics
- [x] Task 10: Harvest dispute rows and objective anchors ([details](phase-03-detached-analysis.md#task-10-harvest-dispute-rows-and-objective-anchors)) (depends on 9)
- [x] Task 11: Detect candidates and derive forward-only lineage ([details](phase-03-detached-analysis.md#task-11-detect-candidates-and-derive-forward-only-lineage)) (depends on 10)
- [x] Task 12: Project the three dispute layers ([details](phase-03-detached-analysis.md#task-12-project-the-three-dispute-layers)) (depends on 10, 11)
- [x] Task 13: Add three metric families and raise the catalog to 154 ([details](phase-03-detached-analysis.md#task-13-add-three-metric-families-and-raise-the-catalog-to-154)) (depends on 10-12)

### Phase 4: Dispute-Resolution Snapshot v1
- [x] Task 14: Define dispute-resolution-snapshot-v1 and its codec ([details](phase-04-snapshot-v1.md#task-14-define-dispute-resolution-snapshot-v1-and-its-codec)) (depends on 10-13)
- [x] Task 15: Add paging, read ports, and cursor support ([details](phase-04-snapshot-v1.md#task-15-add-paging-read-ports-and-cursor-support)) (depends on 14)

### Phase 5: Composition and Durable Publication
- [x] Task 16: Compose completed-run snapshots and receipts ([details](phase-05-composition-publication.md#task-16-compose-completed-run-snapshots-and-receipts)) (depends on 13, 15)
- [x] Task 17: Add the atomic filesystem store and CLI producer ([details](phase-05-composition-publication.md#task-17-add-the-atomic-filesystem-store-and-cli-producer)) (depends on 14-16)

### Phase 6: Read-Only API and Research UI
- [x] Task 18: Add six GET routes, schemas, settings, and app wiring ([details](phase-06-read-only-surfaces.md#task-18-add-six-get-routes-schemas-settings-and-app-wiring)) (depends on 17)
- [x] Task 19: Add the read-only Research UI disputes view ([details](phase-06-read-only-surfaces.md#task-19-add-the-read-only-research-ui-disputes-view)) (depends on 18)

### Phase 7: Invariants, End-to-End Evidence, and Regression
- [x] Task 20: Add the dispute boundary and determinism suite ([details](phase-07-invariants-and-regression.md#task-20-add-the-dispute-boundary-and-determinism-suite)) (depends on 2-19)
- [x] Task 21: Add the dispute end-to-end scenario ([details](phase-07-invariants-and-regression.md#task-21-add-the-dispute-end-to-end-scenario)) (depends on 6-19)
- [x] Task 22: Execute the full V1-V4 regression and qualification lanes ([details](phase-07-invariants-and-regression.md#task-22-execute-the-full-v1-v4-regression-and-qualification-lanes)) (depends on 20, 21)

### Phase 8: Documentation and Final Verification
- [x] Task 23: Execute the documentation checkpoint ([details](phase-08-docs-and-verification.md#task-23-execute-the-documentation-checkpoint)) (depends on 2-22)
- [x] Task 24: Perform final V4-07 verification ([details](phase-08-docs-and-verification.md#task-24-perform-final-v4-07-verification)) (depends on 22, 23)

## Verification Receipt (Tasks 22 and 24)

To be completed by Task 22 and audited by Task 24. Every required lane must be
recorded as exactly one of `executed_passed`, `executed_failed`, or
`unexecuted`. An `unexecuted` lane carries its missing prerequisite and blocks
certification; it is never a skip-pass.

| Lane | State | Evidence |
| --- | --- | --- |
| Python unit + architecture with coverage | `executed_passed` | `pytest tests/unit tests/architecture -q --cov --cov-report=term` → 8183 passed in 2043.20s, total coverage 78%; focused V4-07 selection (`pytest tests/unit/test_dispute_*.py tests/architecture/test_dispute_boundaries.py -q --cov`) → 223 passed, V4-07 modules 81% branch coverage |
| Focused V4-07 suite | `executed_passed` | `pytest tests/unit/test_dispute_*.py tests/architecture/test_dispute_boundaries.py -q` → 223 passed |
| V4/organization/formal-rule regression selection | `executed_passed` | `pytest -k "organization or v4 or formal_rule or dispute or metric_specification or runner_config_v56" tests/unit tests/architecture -q` → 1464 passed, 6719 deselected |
| Documentation parity | `executed_passed` | `pytest tests/unit/test_dispute_docs.py tests/unit/test_formal_rule_docs.py tests/unit/test_organization_docs.py tests/unit/test_organization_operations_docs.py -q` → 32 passed |
| Ruff | `executed_passed` | `ruff check src tests` → all checks passed |
| Mypy | `executed_passed` | `mypy src tests` → success, 1910 source files |
| Import-linter | `executed_passed` | `lint-imports` → 25 kept, 0 broken |
| Integration (`-m "integration and not scale"`) | `executed_passed` | Disposable `pgvector/pgvector:pg17` database `palimpsest_test`; `pytest -m "integration and not scale" -q` → 102 passed |
| Integration including scale | `unexecuted` | Missing prerequisite: the 100,000-tick generational/scale lane was not executed in this session; the disposable pgvector database was available |
| Docker Compose config | `executed_passed` | `docker compose config --quiet` → exit 0 |
| Compose/browser acceptance | `unexecuted` | Missing prerequisites: pinned API image and Playwright chromium; not executed |
| Godot 4.7.2 regression | `unexecuted` | Missing prerequisite: `GODOT_BIN` is unset in this environment; the plan does not change the client |
| Benchmark/scale lane | `unexecuted` | Missing prerequisite: the multi-hour 100,000-tick scale/benchmark harness was not executed in this session |
| Research UI tests | `executed_passed` | `./node_modules/.bin/vitest run` → 51 files, 262 tests passed (pnpm is absent; checked-in binaries used) |
| Research UI type/static checks | `executed_passed` | `svelte-check --tsconfig ./tsconfig.app.json` → 0 errors/0 warnings; `tsc -p tsconfig.node.json` → passed |
| Research UI build | `executed_passed` | `vite build && node scripts/report-build.mjs` → `research_ui_build_ok file_count=5` |

Certification outcome: **not certified**. Four required lanes remain
`unexecuted` with recorded prerequisites: integration including the 100,000-tick
scale lane, Compose/browser acceptance, Godot 4.7.2 regression (`GODOT_BIN`
unset), and the benchmark/scale harness. Every other required lane is
`executed_passed`.

### Task 24 audit

- 24/24 indexed tasks are checked; only this index owns task progress.
- `legal_disputes` is the third owned V4 flag; `_V4_OWNED_CAPABILITY_FLAGS` and
  `V4_OWNED_CAPABILITY_FLAGS` agree; nine flags remain unowned and fail closed.
- Context registry: 14 contexts, 12 flags, `v4-context-map-v2`, four write-pair
  reservations unchanged; `LEGAL_DISPUTES` remains owner-scoped with
  `formal_rules` prerequisite and `uses_existing_events=True`.
- No `runner-config-v57`, no Alembic `0018`, no new event/command/observer
  semantic/write pair/`/v2` route; commands 43, observer semantics 73, replay
  `EVENT_SCHEMA_REPLAY_V22`, codec `v20`, metric families 154.
- Six GET-only `/v1` dispute routes exist; six cursor purposes; six
  `organization` and six `formal-rule` routes keep their paths.
- `dispute-resolution-snapshot-v1` and `dispute-resolution-store-v1` are
  independent; organization v1/v2/v3 and `formal-rule-snapshot-v1` regression
  tests stay green.
- `WorldEngine`/admission never reads a dispute ledger; the E2E proves a
  socially disputed but physically possible command is admitted while a
  physically impossible command is rejected.
- `.ai-factory/RULES.md` was not edited. `.ai-factory/ROADMAP.md` was not edited
  during implementation; after verification `$aif-roadmap` registered V4-07 in
  M8 as implemented with certification withheld for the four unexecuted lanes.
- `docs/disputes.md` is the canonical documentation contract; the former
  `docs/dispute-resolution.md` path remains a compatibility landing page, and
  README plus every cross-link point to `docs/disputes.md`. Documentation-count
  parity checks now assert the current 154-family pin.

## Commit Plan

Proposed implementation checkpoints; no commit is made by planning.

1. After Tasks 1-3: `feat(v4): own the legal-disputes capability contract`
2. After Tasks 4-6: `feat(v4): record owner-scoped dispute claims`
3. After Tasks 7-9: `feat(v4): resolve disputes without a justice oracle`
4. After Tasks 10-13: `feat(v4): analyze disputes and objective alignment`
5. After Tasks 14-17: `feat(v4): publish dispute-resolution-snapshot-v1`
6. After Tasks 18-19: `feat(v4): serve read-only disputes`
7. After Tasks 20-24: `test(v4): enforce dispute-resolution invariants`

## Blocking Conditions and Non-Goals

- Adding `runner-config-v57`, a new V4 flag, a new runner root field, or a
  per-agent runner mode to make this plan work is a blocking scope violation.
  Stop and re-plan.
- Creating an objective Court, Judge, Jury, Jurisdiction, Verdict, Judgment,
  LegalCode, Statute, JusticeEngine, ArbitrationEngine, SanctionEngine,
  LiabilityEngine, global dispute registry, or authoritative case file is
  forbidden.
- Letting `WorldEngine`, perception, admission, stop selectors, memory, prompts,
  observer semantics, or the Godot client read a dispute ledger is forbidden.
- Letting a dispute helper return, construct, submit, or resolve an
  `AgentCommand`, move a resource, or execute a physical action is forbidden.
  The only supported undertaking path delegates to the existing
  `compile_mediation_undertaking`.
- Treating a claim, testimony, rule reference, authority reference, mediation
  recommendation, proposed resolution, acceptance, or rejection as objective
  truth, permission, prohibition, guilt, liability, or a binding settlement is
  forbidden.
- Inferring a claim, counterclaim, acceptance, rejection, or violation from
  silence or from an unobserved act is forbidden.
- Reconciling two owners' conflicting memories into one authoritative account is
  forbidden. Analysis may classify alignment for researchers only.
- Adding a new event, command, observer semantic type, write pair, artifact kind,
  durable-record genre, `/v2` route, `observer-protocol-v2` serving, or SQL
  migration is forbidden.
- Rewriting the V3 mediation, structured-commitment, subjective-value,
  institution, office, durable-record, or V4 organization/formal-rule contracts
  is forbidden; disputes are additive.
- Weakening an existing pin or assertion (catalog counts, Alembic `0017`,
  replay v22, codec v20, command count, observer semantic count, context count)
  is forbidden. The only intentional pin changes are 151 → 154 metric families,
  the addition of six dispute routes alongside the six organization and six
  formal-rule routes, and the owned-flag set 2 → 3.
- Claiming prevalence, emergence probability, predictive power, capacity,
  throughput, moral correctness, or a composite civilization score is
  forbidden.
- Editing `.ai-factory/ROADMAP.md` or closing M8 is out of scope;
  `$aif-roadmap` owns that.
- Changing the Godot client, observer protocol, observer capabilities, or
  `/version` is out of scope; the Research UI is the only client change.
- Enabling V4 flags in matrix lanes is out of scope; `experiments.matrix_schema`
  keeps its rejection gate.
- Full qualification requires a disposable PostgreSQL/pgvector instance,
  Docker, a real browser driver, and the pinned Node/pnpm and Godot toolchains.
  A missing prerequisite leaves the lane unexecuted and blocks certification; it
  never becomes a skip-pass.
- Do not implement any other V4 context (`diplomacy`, `organized_conflict`,
  `infrastructure_networks`, `supply_chains`, `markets_credit`, `science`,
  `epidemics`, `ecological_feedback`, `disasters`, `societal_resilience`,
  `macro_society_identity`, or another organization extension) in this plan.

## Definition of Done

- All 24 indexed tasks have verified completion evidence; only this index holds
  task progress checkboxes.
- `legal_disputes` is the third owned V4 flag on `runner-config-v56`; no `v57`,
  new flag, root field, or per-agent runner key exists.
- The context registry validates at 14 contexts, 12 flags, and
  `v4-context-map-v2`; the analysis-only set and four reservations are
  unchanged.
- A dispute is an owner belief with attributed claims, counterclaims, testimony,
  evidence references, rule references, mediation links, authority references,
  proposed resolutions, and per-party accepted/rejected declarations.
- The six requested dispute kinds plus the closed `other` fallback are
  representable; opposing claims and conflicting memories coexist without
  reconciliation.
- Testimony independence is explicit; shared roots never count as independent
  corroboration.
- Rule references resolve only against the owner's formal-rule ledger; missing or
  mismatched rules remain orphaned or version-mismatched.
- Mediation cases, recommendations, responses, and outcomes are linked as
  beliefs; no binding mediation decision is created.
- Institutional roles are cited through existing office, institution,
  organization, collective-decision, procedure, or record beliefs; no court,
  judge, or jurisdiction exists.
- Resolutions are proposals; `apparently_accepted` requires every named party's
  active declaration and binds nobody. Acceptance requires a proposal observed in
  a prior committed tick; same-tick acceptance is refused with
  `dispute_resolution_requires_prior_tick`.
- No dispute helper constructs, submits, or executes a command; the only
  undertaking path reuses `compile_mediation_undertaking`.
- `WorldEngine` never reads a dispute ledger; a socially disputed but physically
  possible command is still admitted, and a physically impossible command is
  still rejected by the existing rules.
- Evidence references carry no `WorldEvent`, `WorldState`, event store, or peer
  ledger; observed occurrences/communications carry only opaque `EventId`
  correlation.
- Detached analysis may join objective history for researcher-only alignment;
  agents never receive that alignment, and no verdict/guilt/liability value
  exists.
- Detached analysis never creates an objective dispute or changes a
  formal-rule/organization/mediation candidate; objective counts, owner claims,
  and analytical summaries remain separate.
- The metric catalog is exactly 154 with three appended families; the first 151
  are unchanged, and real completed-run assembly emits all three documents.
- `dispute-resolution-snapshot-v1` is canonical, bounded, immutable after
  publication, and organization/formal-rule snapshots remain decodable and
  byte-verifiable.
- Public dispute contracts are exported from `agents.cognition`, `simulation`,
  `experiments`, and `persistence`; tests narrow shared `object` result fields
  before attribute access.
- The read port is run-id/filter/offset based and mirrors `FormalRuleReadPort`;
  cursor packaging and expiry live only in the API cursor codec.
- Six GET-only `/v1` dispute routes require `SUBJECTIVE_DEBUG`, have an explicit
  `dispute_disabled` state, and are consumed by a read-only Research UI view.
- Cursor reuse works on every paged dispute route; changed
  filter/run/publication/digest fails with 400 and expiry with 410.
- The boundary suite proves owner-only authority, absence of magic actors,
  justice engines, courts, juries, verdicts, global registries, objective
  jurisdictions, command construction, and world-ledger reads; no new
  commands/events/migrations are added; observer/migration pins are unchanged.
- The full V1-V4 regression lanes and static gates execute and pass; any
  unexecuted required lane is reported with its blocker and is not certified.
- Documentation states what a dispute controls (a belief), what it never
  controls (objective action), how memory-dependent disagreement works, how
  testimony independence and rule references work, how mediation and
  institutional roles are linked, how resolutions are proposed and declared,
  and every count matches the code.
