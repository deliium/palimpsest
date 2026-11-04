<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-09 Delegation and Representation

Mode: ultra
Branch: main
Created: 2026-11-04
Plan identifier: `v4-09-delegation-representation`

## Original Request

v4-09 delegation and representation

Naming requirement:

Use `v4-09-delegation-representation`.

Implement socially recognized delegation.

An agent may claim or receive authority to act/speak for:

- another agent

- organization

- settlement

- coalition

Represent:

delegator
representative
scope
duration
support
opposition
revocation
provenance

Do NOT make representation automatically legitimate.

Some members may reject the representative.

Enable:

negotiators
messengers
project coordinators
organizational representatives

Integrate representation with collective decisions and later diplomacy.

## Settings

- Testing: yes; full strategy. Unit, architecture, determinism, integration,
  Compose/browser, Godot regression, Research UI, benchmark regression, and
  static gates, with coverage enabled for Python lanes.
- Logging: verbose, metadata-only. Bounded DEBUG flow/counts, INFO milestones,
  WARN incomplete representation/truncation, ERROR safe codes.
  `PALIMPSEST_LOG_LEVEL` controls operational verbosity. Never log principal
  references, representative or actor identities, mandate ids, scope subjects,
  support/opposition sets, revocation provenance, decision/office references,
  frame bodies, prompts, credentials, tokens, DSNs, memories, embeddings,
  utterance bodies, labels, or payload surrogates.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 23.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints are suggestions, not authorization to
  commit during planning.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-09-delegation-representation`; the ultra bundle
  directory is `.ai-factory/plans/v4-09-delegation-representation/`, phase files
  use `phase-NN-<slug>.md`, and `index.md` is the canonical entrypoint.
- Research source: `.ai-factory/RESEARCH.md` and `.ai-factory/research/` do not
  exist; no external research conclusions are invented.
- Execution: plan only. No implementation, commit, roadmap edit, or branch
  creation occurs in this invocation.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"
Rationale: V4-09 deepens the owned, owner-scoped `organizations` V4 context with
a general representation ledger covering principals, representatives, scope,
duration, support, opposition, revocation, and provenance, while keeping
recognition a belief and adding no capability flag, runner schema, command,
event, observer semantic type, write pair, `/v2` route, or migration. `diplomacy`
already declares `organizations` as its prerequisite, so this work prepares the
later diplomacy plan without claiming it. This plan does not edit or close the
roadmap; `$aif-roadmap` must register V4-09 in M8.

## Requirements Reconciliation

Authority: the Original Request defines scope; `.ai-factory/ARCHITECTURE.md`
("Key Principles", "Capability ownership", "Important V3 seams", "Versioned
Extension Contract", V4-01 through V4-08 seams) and `.ai-factory/RULES.md`
constrain every edit; `.ai-factory/DESCRIPTION.md` and `.ai-factory/ROADMAP.md`
describe current state; completed V2/V3 mediation, collective-decision,
structured-commitment, institution, office, organization, operation, collective
agency, formal-rule, dispute, and V4-08 evidence code plus
`tests/architecture/test_v4_architecture_invariants.py`,
`test_organization_*`, `test_formal_rule_boundaries`, `test_dispute_boundaries`,
and `test_evidence_testimony_boundaries` govern compatibility. V4-09 creates no
capability flag and no new context: it deepens the existing `organizations` flag.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-09 deepens the owned `organizations` context; no other V4 flag, `runner-config-v57`, new root field, or per-agent runner key is added | Original Request "socially recognized delegation"; `.ai-factory/ARCHITECTURE.md` "Capability ownership"; `src/simulation/v4_architecture.py` 103-121, 324-326; `src/simulation/runner_models.py` 305-325, 1114-1163, 7964-7976 | Task 2/3 tests; Task 20 pins; Task 24 `v57` absence |
| Representation is a cross-cutting social belief and is attachable to the collective context: `diplomacy` already requires `organizations`, so this work prepares diplomacy without claiming it | `.ai-factory/ROADMAP.md` M8 "Next plans"; `src/simulation/v4_architecture.py` 150-163; `.ai-factory/ARCHITECTURE.md` "Capability ownership" | Task 2/24 ownership audit |
| The representation ledger is active exactly when `organizations` is enabled on `runner-config-v56`; `organizations` remains one of the three owned flags | `src/simulation/runner.py` 1029-1031, 1366-1397; `src/simulation/runner_models.py` 320-325 | Task 2/3/9 tests |
| Principal kinds are closed: `agent`, `organization`, `settlement`, `coalition`, plus `unknown`; each non-agent kind requires an existing owner-safe anchor | Original Request principal list; `src/agents/cognition/organization_concepts.py` 31, 373; `src/world/observations.py` 283-324, 333-374 | Task 1/4/6/7 tests |
| A settlement anchor is an owner-visible region id; no objective settlement, polity, or citizenship object is created | `.ai-factory/ARCHITECTURE.md` "Important V3 seams"; `src/world/observations.py` 333-374; `src/simulation/v4_architecture.py` 150-163 | Task 4/7/21 tests |
| An organization or coalition anchor is the owner's own `orgc-` collective concept; a missing concept leaves the claim unresolved instead of inventing a collective | `src/agents/cognition/organization_concepts.py` 31, 373, 973-1010; `.ai-factory/ARCHITECTURE.md` V4-03 seam | Task 4/6/7/12 tests |
| Representation is never automatically legitimate: recognition requires a principal act, independent support, or an office/decision/written basis, with opposition able to reject or contest | Original Request "Do NOT make representation automatically legitimate" / "Some members may reject"; `src/agents/cognition/offices.py` 579-667, 1143-1195 | Task 7/8/20/21 tests |
| Scope is a closed belief, never a permission; no representation helper returns, constructs, submits, or resolves an `AgentCommand` | Original Request "scope"; `.ai-factory/ARCHITECTURE.md` Key Principle 1; `src/agents/cognition/legal_disputes.py` 2517-2544 | Task 1/6/20 tests |
| Duration is closed and expiry is deterministic (`single_act`, `occasion`, `until_tick`, `until_revoked`, `unknown`) | Original Request "duration"; `src/agents/cognition/collective_decisions.py` 705-719 (proposal windows) | Task 1/4/8 tests |
| Support, opposition, abstention, and revocation are retained owner beliefs with provenance; nothing is deleted | Original Request "support/opposition/revocation/provenance"; `src/agents/cognition/offices.py` 579-667 | Task 4/6/8/12 tests |
| Same-root retellings are not independent support; the owner's self-support never counts | `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts"; `src/agents/cognition/offices.py` 1934-1983 | Task 7/12/21 tests |
| A speaker cannot attribute a mandate to another party; frames are verified against the actual speaker | Original Request provenance; `src/agents/cognition/evidence_testimony_communication.py` 491-507; `src/agents/cognition/legal_disputes.py` 3619-3629 | Task 5/6/20 tests |
| Representation composes with collective decisions instead of duplicating decision delegation: V3-31 delegation stays proposal-scoped, and representation consults the owner's decision ledger read-only | Original Request "Integrate representation with collective decisions"; `src/agents/cognition/collective_decisions.py` 152-160, 705-719 | Task 7/8/21 tests |
| Reconciliation adds no new cognition mode to the runner schema; the mode is flag-derived inside the existing organizations branch | `src/simulation/runner.py` 1366-1397; `src/agents/cognition/configuration.py` 647-658 | Task 2/3/9 tests |
| The owner's ledger reaches `Perspective` through `build_perspective` and `SimulationRunnerResult` validates ordered ledger sequences | `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime"; `src/simulation/perception.py` 113-162; `src/simulation/runner_models.py` 6377-6382, 6698-6723 | Task 9 tests; Task 20 carry scan |
| Detached analysis keeps objective counts, owner rows, and analytical candidates in three separate types with a hard leakage guard | `.ai-factory/ARCHITECTURE.md` Key Principle 1; `src/analysis/evidence_testimony_layers.py` 153-199 | Task 12/20 tests |
| Researcher-only scope alignment (`consistent`, `unresolved`, `inconsistent`, `not_applicable`) never reaches cognition, prompts, memory, world state, stop selectors, or observer semantics | Original Request; `.ai-factory/ARCHITECTURE.md` "analysis is read-only" | Task 12/20/21 tests |
| The metric catalog grows from 157 to 160 by appending `representation_mandate_structure@1`, `representation_recognition_support@1`, and `representation_scope_alignment@1`; the first 157 keep id, order, version, and value keys | `src/analysis/specifications.py` 53, 232-234, 7369-7371 | Task 13/20/24 pin checks |
| Raising the catalog sweeps every hard-coded pin: 68 metric-count assertions in 44 test files and the current-pin lines in `docs/analysis-metrics.md`, `docs/architecture.md`, and `docs/disputes.md` move to 160; historical revision statements and the first-154 digest stay unchanged | `tests/unit`, `tests/architecture` (`grep "== 157"`), `docs/analysis-metrics.md:41`, `docs/architecture.md:565/596/634`, `docs/disputes.md:225` | Task 13 sweep + stale-pin guard; Task 20/23 re-run |
| Snapshot rows and API responses expose hashed `owner_token`/`principal_token`/`representative_token`/`actor_token` only; no raw agent id or free-text scope subject is published | `.ai-factory/ARCHITECTURE.md` Key Principle 5; `src/analysis/evidence_testimony_rows.py` safe-token pattern; `src/api/evidence_testimony_schemas.py` | Task 14/18/20/21 tests |
| `delegation-representation-snapshot-v1` is a new independent artifact; dispute, evidence, organization, and formal-rule snapshots remain byte-verifiable and unchanged | `.ai-factory/ARCHITECTURE.md` "Use accepted-set and exact-key-set schema evolution"; `src/simulation/evidence_testimony_codec.py` 344-488 | Task 14/20/24 snapshot tests |
| Access is six GET-only `/v1/simulations/{run_id}/representation...` routes requiring `SUBJECTIVE_DEBUG`; the organization, formal-rule, dispute, and evidence route sets keep their paths | `docs/research-api.md`; `src/api/routes/evidence_testimony.py` 43, 218-451 | Task 18/20 route tests; Task 21 API reads |
| Cursors bind to the publication digest and query fingerprint; changed run/filter/publication/digest fails with 400 and expiry with 410 | `src/api/evidence_testimony_cursor.py` 26-138; `src/simulation/evidence_testimony_ports.py` 39-164 | Task 15/18/21 cursor tests |
| Publication is opt-in, post-completion, atomic, quota-bounded, and isolated from scientific status; new CLI flags and env root follow the evidence precedent | `src/experiments/evidence_testimony_publication.py` 57-341; `src/persistence/evidence_testimony_filesystem.py` 52-327; `src/research_runner/evidence_testimony_composition.py` 39-185 | Task 16/17/21 receipts and failure-isolation tests |
| No SQL migration, new event, command, observer semantic type, write pair, `/v2` route, or `observer-protocol-v2` is added; Alembic stays `0017`, events 22, codec v20, commands 43, semantics 73 | `.ai-factory/ARCHITECTURE.md` requirements 4-6; `src/simulation/versioning.py` 77-90 | Task 20/24 pins |
| Representation rows flow through `MetricComputationInputs`, `experiments.collectors`, and `analysis.metric_service`; the new families are emitted by real completed-run assembly | `.ai-factory/ARCHITECTURE.md` "analysis is read-only"; `src/analysis/metric_service.py` 1706-1784; `src/experiments/collectors.py` 827-845 | Task 10/13 tests; Task 21 metric assembly |
| Required lanes must execute; a missing prerequisite is reported `unexecuted` with a prerequisite, never as a skip-pass | Plan Settings "Testing: yes; full strategy"; `docs/development.md`; `tests/compose/acceptance.py` | Task 22 three-state receipt; Task 24 audit |
| The roadmap is owned by `$aif-roadmap` and is not edited here | `.ai-factory/ARCHITECTURE.md` requirement 7 | Task 23/24 `git status` |

### Supported combinations and availability transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| Default runner config, all V4 flags off | V4-08-equivalent behavior | No representation ledger, no metric, no publication, no route data | Task 3/9/21 flags-off tests |
| `organizations` enabled on v4 or v55 | Unchanged config | `v4_capability_requires_v56` before construction | Task 2 test |
| `organizations` enabled on v56 | Valid run | Representation mode DETERMINISTIC; ledger active | Task 3/9 test |
| `formal_rules` or `legal_disputes` alone | Valid run | Representation stays DISABLED | Task 3 test |
| `diplomacy` enabled | No behavior change | Still fails closed with `capability_unimplemented` | Task 2/24 test |
| Agent principal claim | Owner-local mandate | `rmd-` with `principal_resolved=True`; status `claimed` | Task 4/6/7 tests |
| Organization principal with owned `orgc-` concept | Resolved collective | Anchor resolves; recognition depends on support/act | Task 7 test |
| Organization principal without an owned concept | Unresolved claim | `claimed` + `representation_unresolved_principal`; no invented concept | Task 7 test |
| Coalition principal with owned `orgc-` concept | Resolved collective | Same path as organization; no coalition entity exists | Task 7/12 test |
| Settlement principal with a visible region id | Resolved place | Region anchor retained; status derived from support | Task 7/21 test |
| Settlement principal with no observed region | Unresolved claim | `claimed` + `representation_region_unavailable` | Task 7 test |
| Representative self-claims | Owner belief | `claimed` only; never `recognized` without principal act or support | Task 7/20 tests |
| Agent principal delegates to another agent | Principal act | `recognized` / `principal_declaration`; representative must differ from principal | Task 5/6/7/21 tests |
| Principal accepts as the verified agent | Principal act | `recognized` / `principal_declaration` | Task 6/7/21 tests |
| Collective principal "accepts" through a member frame | Support position | Recorded as `communicated` support, not principal acceptance | Task 5/6 tests |
| Two independent supporters | Independent support | `recognized` / `independent_support` when opposition is lower | Task 7 test |
| Two supporters sharing one root | One independence key | Still `claimed`/`contested`; no independent corroboration | Task 7/12 tests |
| One supporter and one opposer | Contested | `contested`; both rows retained | Task 7/21 test |
| Opposition at least equal to support | Rejection | `rejected`; retained, revisable by later positions | Task 7 test |
| Principal revokes | Revocation | `revoked`; positions and revocation retained | Task 8/21 test |
| Representative resigns | Revocation | `revoked` with `representative_resigned` | Task 8 test |
| Unauthorized third-party revocation | Contest | `revocation_dispute` conflict; mandate unchanged | Task 8 test |
| `until_tick` boundary tick | Expiry | `expired` at `end_tick`; row retained | Task 8 test |
| Two mandates for one principal/scope | Coexistence | Both retained; `duplicate_mandate` when both recognized | Task 8/21 test |
| New recognized mandate replaces a claimed one | Supersession | Older `superseded`; history retained | Task 8 test |
| Frame from a claimed but different speaker | Rejected frame | `representation_party_mismatch`; no row created | Task 5/6/20 tests |
| Malformed or over-cap frame | Dropped frame | `representation_frame_dropped`; no body logged | Task 5/6 tests |
| Communication-mapped scope with an act in-window | Researcher-only alignment | `consistent`; agent ledger unchanged | Task 12/20/21 tests |
| Communication-mapped scope with acts only out-of-window | Researcher-only alignment | `inconsistent`; no verdict or revocation | Task 12/20 test |
| No attributable act | Researcher-only alignment | `unresolved` | Task 12 test |
| `transact`/`decide`/`coordinate_project`/unknown scope | No objective referent | `not_applicable`; never counted as consistent | Task 12 test |
| Candidate exceeds 32 mandates or 320 records | Deterministic truncation | `representation_truncated` on terminal rows; `representation_capacity_reached` when nothing droppable; no silent drop | Task 4/14/16 tests |
| Snapshot exceeds 8192 mandates / 16384 positions / 4 MiB | No publication | `representation_size_limit` | Task 14/16 tests |
| Duplicate publication id with different bytes | Existing publication untouched | `representation_publication_exists` | Task 17 test |
| `PALIMPSEST_REPRESENTATION_ROOT` unset | API state unset | 503 `representation_disabled`; CLI receipt `disabled` | Task 18/21 tests |
| Cursor reused with same filter/run/publication/digest | Same page | 200; digest matches | Task 15/18 test |
| Cursor reused with changed filter/run/publication/digest | No page served | 400 `representation_cursor_invalid`; expired 410 | Task 15/18 test |
| Run incomplete or publication failed | Scientific result unchanged | Receipt `unavailable`/`failed` only | Task 16/17/21 test |
| Required Compose/browser/Godot/benchmark lane with a missing prerequisite | No green certification | Recorded `unexecuted` with prerequisite | Task 22/24 |

No blocking open questions: every material decision is fixed below.

## Architecture and Decisions

1. **One owned flag, one deepening.** V4-09 adds no V4 flag, context,
   `runner-config-v57`, runner root field, or per-agent runner key. The
   representation ledger is active exactly when `organizations` is enabled on
   the accepted `runner-config-v56` seam.
2. **Representation is a belief about standing.** Every row belongs to one owner
   and describes whom that owner believes may act or speak for a principal. There
   is no representative registry, legitimacy oracle, or permission service.
3. **Principal kinds are closed.** `agent`, `organization`, `settlement`,
   `coalition`, and `unknown` are the only kinds. Organization and coalition
   require an existing owner-local `orgc-` concept; settlement requires an
   owner-visible region id; unknown has no anchor.
4. **No invented collectives.** A missing concept or region leaves the claim
   unresolved; it is never resolved by inference, a peer ledger, or a
   settlement/coalition registry.
5. **Scope is not permission.** `speak_for`, `negotiate`, `carry_message`,
   `coordinate_project`, `transact`, `decide`, and `unknown` describe what the
   owner believes the representative may do. No scope value makes a command
   admissible.
6. **Duration is explicit.** Single-act, occasion, until-tick, and until-revoked
   mandates expire deterministically; expiry is a retained state.
7. **Support and opposition are independent beliefs.** One active position per
   actor per mandate; same-root positions count once; the owner's self-support is
   excluded.
8. **Recognition is derived, not asserted.** Principal act, office/decision/
   written basis with a root, or two independent support roots can recognize;
   opposition can contest or reject. A self-claim alone stays claimed.
9. **Rejection is legal and retained.** Members may reject a representative;
   rejection never deletes a mandate and never becomes a truth finding.
10. **Revocation is authorized and retained.** Principal revocation,
    representative resignation, collective-decision revocation, office loss, and
    expiry are recorded; unauthorized revocation attempts become conflicts.
11. **Conflicts coexist.** Duplicate mandates, contradictory scopes, conflicting
    principals, and revocation disputes stay `unresolved`; two recognized
    mandates may coexist.
12. **Speech is the only claim channel.** Bounded `rep_v1` frames travel inside
    existing `Talk`/`Ask`/`Tell`; the verified speaker must match the claimed
    principal or representative role.
13. **Composition, not duplication.** V3-31 decision delegation stays
    proposal-scoped; V4-09 representation is standing to act/speak. The ledger
    consults decision/office/rule ledgers read-only and never mutates them.
14. **Diplomacy-ready, not diplomacy.** `representation_standing_summary` is a
    read-only projection for a later plan; V4-09 adds no diplomacy context, flag,
    treaty, negotiation protocol, or polity object.
15. **No command path.** No representation helper constructs, submits, resolves,
    or executes an `AgentCommand`; every physical effect remains an ordinary
    admitted command.
16. **Three layers, three types.** Objective rows are aggregate committed-act
    counts; subjective rows use hashed owner tokens and status counts; analytical
    rows use `rep-` candidates. Leakage is a hard failure.
17. **No objective alignment in cognition.** `consistent`, `unresolved`,
    `inconsistent`, and `not_applicable` exist only in detached analysis and
    never reach prompts, memory, world state, stop selectors, or observer
    semantics.
18. **A new snapshot, not a rewrite.** `delegation-representation-snapshot-v1`
    is independent; dispute, evidence, organization v1/v2/v3, and formal-rule
    snapshots remain decodable and byte-verifiable.
19. **Metrics append only.** 157 → 160. The first 157 keep id, order, version,
    and value keys.
20. **Deterministic by construction.** Sorted ordering, content-addressed ids,
    canonical JSON digests, quantized confidence, integer support counts, no
    `hash()`, no UUID, and no wall-clock domain values.
21. **Read-only surfaces.** Six GET routes under `/v1` require
    `SUBJECTIVE_DEBUG`; the Research UI renders server fields without deriving
    legitimacy, authority, or a winning representative.
22. **Cursors bind to the publication digest.** Every paged route binds run,
    publication, digest, purpose, and filters.
23. **Publication is opt-in and non-interfering.** A storage or composition
    failure changes only the receipt, never the scientific result.
24. **No automatic generalization.** V4-09 implements no diplomacy,
    organized conflict, market, supply chain, science, infrastructure, epidemic,
    ecological, disaster, resilience, or macro-society behavior.
25. **Published identities are tokens.** Snapshot rows and API responses carry
    hashed owner/principal/representative/actor tokens; raw agent ids and
    free-text scope subjects never leave the owner's private ledger.

### Context declaration

| Context | Flag | Authority | Owning packages | Prerequisites | Existing mechanism | Event strategy |
| --- | --- | --- | --- | --- | --- | --- |
| `organizations` (deepened) | `organizations` (already owned) | owner-scoped | `agents.cognition`, `social`, `simulation` | none | organization concepts, operations, collective agency, offices, collective decisions, formal rules, reputation, relationships | reuse |

Supporting packages without authority: `analysis` (detached rows/metrics),
`experiments` (harvest/publication bridge), `persistence` (filesystem store),
`api` (read-only routes), `research_runner` (opt-in CLI producer), and the
Research UI client.

### Compatibility pins

Default runner/result `v4`/`v2`; latest feature runner `v55`; accepted runner adds
`v56` only; events `EVENT_SCHEMA_REPLAY_V22` (22); codec `v20`; commands 43;
observer semantic types 73; metric families **160 (V4-09 change)**; Alembic
`0017`; `/v1`; `observer-protocol-v1`; observer layout `observer-layout-v1`;
observer capabilities 4 advertised / 6 reserved; four reserved write pairs
(events 23-26 / codecs `v21`-`v24`); `prepare_parallel=False`; six GET
organization routes, six GET formal-rule routes, six GET dispute routes, six GET
evidence routes, and six GET representation routes; six cursor purposes per
context; snapshots `organization-snapshot-v1`/`v2`/`v3`,
`formal-rule-snapshot-v1`, `dispute-resolution-snapshot-v1`,
`evidence-testimony-snapshot-v1`, and `delegation-representation-snapshot-v1`;
stores `organization-store-v1`, `formal-rule-store-v1`,
`dispute-resolution-store-v1`, `evidence-testimony-store-v1`, and
`delegation-representation-store-v1`; 14 V4 contexts / 12 flags / **3 owned
flags**. `diplomacy`, `institutional_economy`, and
`multi_hop_testimony_tracking` remain unowned and fail closed. `/version` is
unchanged; `organization_rows` remains reserved.

## Phase Index

1. [Phase 1: Contract and Seam](phase-01-contract-and-seam.md) — Tasks 1-3
2. [Phase 2: Owner-Scoped Representation Beliefs](phase-02-representation-beliefs.md) — Tasks 4-9
3. [Phase 3: Detached Analysis, Candidates, and Metrics](phase-03-detached-analysis.md) — Tasks 10-13
4. [Phase 4: Delegation-Representation Snapshot v1](phase-04-snapshot-v1.md) — Tasks 14-15
5. [Phase 5: Composition and Durable Publication](phase-05-composition-publication.md) — Tasks 16-17
6. [Phase 6: Read-Only API and Research UI](phase-06-read-only-surfaces.md) — Tasks 18-19
7. [Phase 7: Invariants, End-to-End Representation, and Regression](phase-07-invariants-and-regression.md) — Tasks 20-22
8. [Phase 8: Documentation and Final Verification](phase-08-docs-and-verification.md) — Tasks 23-24

## Cross-Phase Dependencies

- All phases assume the completed V2/V3 mediation, decision, office,
  institution, organization, operation, collective-agency, formal-rule, dispute,
  and V4-08 evidence stacks are present; V4-09 does not rewrite them, but Tasks
  20/22 must keep their suites green.
- Task 2 depends on Task 1: the ownership pin uses the frozen vocabulary.
- Task 3 depends on Task 2: the mode and policy reference the owned flag.
- Task 4 depends on Task 3: records use the policy, ids, and limits.
- Task 5 depends on Task 4: `rep_v1` frames encode the record vocabulary.
- Task 6 depends on Tasks 4-5: the update consumes the frame parser and records.
- Task 7 depends on Task 6: recognition consumes materialized mandates, positions,
  and sidecars.
- Task 8 depends on Tasks 6-7: conflicts, revocation, expiry, and supersession
  consume mandates and recognition inputs.
- Task 9 depends on Tasks 4-8: runtime carry needs records, frames, recognition,
  and revocation.
- Task 10 depends on Task 9: harvest reads exported ledgers and committed acts.
- Task 11 depends on Task 10: detection/identity consumes normalized rows.
- Task 12 depends on Tasks 10-11: layers and alignment consume rows, candidates,
  and identity assignments.
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
- Task 21 depends on Tasks 6-19: the E2E uses the real update, speech frames,
  recognition, publication, and surfaces.
- Task 22 depends on Tasks 20-21: regression runs after the invariant/E2E gates.
- Task 23 depends on Tasks 2-22: documentation describes verified surfaces.
- Task 24 depends on Tasks 22-23: final certification needs receipts and docs.

## Tasks

### Phase 1: Contract and Seam
- [x] Task 1: Freeze the delegation-representation vocabulary and identity grammar ([details](phase-01-contract-and-seam.md#task-1-freeze-the-delegation-representation-vocabulary-and-identity-grammar))
- [x] Task 2: Pin the organizations deepening seam ([details](phase-01-contract-and-seam.md#task-2-pin-the-organizations-deepening-seam)) (depends on 1)
- [x] Task 3: Add the cognition representation mode and policy seam ([details](phase-01-contract-and-seam.md#task-3-add-the-cognition-representation-mode-and-policy-seam)) (depends on 2)

### Phase 2: Owner-Scoped Representation Beliefs
- [x] Task 4: Define representation records and ledger invariants ([details](phase-02-representation-beliefs.md#task-4-define-representation-records-and-ledger-invariants)) (depends on 3)
- [x] Task 5: Add bounded rep_v1 delegation speech frames ([details](phase-02-representation-beliefs.md#task-5-add-bounded-rep_v1-delegation-speech-frames)) (depends on 4)
- [x] Task 6: Collect mandates, positions, and revocations ([details](phase-02-representation-beliefs.md#task-6-collect-mandates-positions-and-revocations)) (depends on 4, 5)
- [x] Task 7: Resolve principals and derive owner recognition ([details](phase-02-representation-beliefs.md#task-7-resolve-principals-and-derive-owner-recognition)) (depends on 6)
- [x] Task 8: Retain conflicts, revocation, and supersession ([details](phase-02-representation-beliefs.md#task-8-retain-conflicts-revocation-and-supersession)) (depends on 6, 7)
- [x] Task 9: Carry the ledger through cognition and runtime ([details](phase-02-representation-beliefs.md#task-9-carry-the-ledger-through-cognition-and-runtime)) (depends on 4-8)

### Phase 3: Detached Analysis, Candidates, and Metrics
- [x] Task 10: Harvest representation rows and objective speech anchors ([details](phase-03-detached-analysis.md#task-10-harvest-representation-rows-and-objective-speech-anchors)) (depends on 9)
- [x] Task 11: Detect candidates and derive forward-only lineage ([details](phase-03-detached-analysis.md#task-11-detect-candidates-and-derive-forward-only-lineage)) (depends on 10)
- [x] Task 12: Project layers and researcher-only scope alignment ([details](phase-03-detached-analysis.md#task-12-project-layers-and-researcher-only-scope-alignment)) (depends on 10, 11)
- [x] Task 13: Add three metric families and raise the catalog to 160 ([details](phase-03-detached-analysis.md#task-13-add-three-metric-families-and-raise-the-catalog-to-160)) (depends on 10-12)

### Phase 4: Delegation-Representation Snapshot v1
- [x] Task 14: Define delegation-representation-snapshot-v1 and its codec ([details](phase-04-snapshot-v1.md#task-14-define-delegation-representation-snapshot-v1-and-its-codec)) (depends on 10-13)
- [x] Task 15: Add paging, read ports, and cursor support ([details](phase-04-snapshot-v1.md#task-15-add-paging-read-ports-and-cursor-support)) (depends on 14)

### Phase 5: Composition and Durable Publication
- [x] Task 16: Compose completed-run snapshots and receipts ([details](phase-05-composition-publication.md#task-16-compose-completed-run-snapshots-and-receipts)) (depends on 13, 15)
- [x] Task 17: Add the atomic filesystem store and CLI producer ([details](phase-05-composition-publication.md#task-17-add-the-atomic-filesystem-store-and-cli-producer)) (depends on 14-16)

### Phase 6: Read-Only API and Research UI
- [x] Task 18: Add six GET routes, schemas, settings, and app wiring ([details](phase-06-read-only-surfaces.md#task-18-add-six-get-routes-schemas-settings-and-app-wiring)) (depends on 17)
- [x] Task 19: Add the read-only Research UI representation view ([details](phase-06-read-only-surfaces.md#task-19-add-the-read-only-research-ui-representation-view)) (depends on 18)

### Phase 7: Invariants, End-to-End Representation, and Regression
- [x] Task 20: Add the representation boundary and determinism suite ([details](phase-07-invariants-and-regression.md#task-20-add-the-representation-boundary-and-determinism-suite)) (depends on 2-19)
- [x] Task 21: Add the representation end-to-end scenario ([details](phase-07-invariants-and-regression.md#task-21-add-the-representation-end-to-end-scenario)) (depends on 6-19)
- [x] Task 22: Execute the full V1-V4 regression and qualification lanes ([details](phase-07-invariants-and-regression.md#task-22-execute-the-full-v1-v4-regression-and-qualification-lanes)) (depends on 20, 21)

### Phase 8: Documentation and Final Verification
- [x] Task 23: Execute the documentation checkpoint ([details](phase-08-docs-and-verification.md#task-23-execute-the-documentation-checkpoint)) (depends on 2-22)
- [x] Task 24: Perform final V4-09 verification ([details](phase-08-docs-and-verification.md#task-24-perform-final-v4-09-verification)) (depends on 22, 23)

## Verification Receipt (Tasks 22 and 24)

To be completed by Task 22 and audited by Task 24. Every required lane must be
recorded as exactly one of `executed_passed`, `executed_failed`, or
`unexecuted`. An `unexecuted` lane carries its missing prerequisite and blocks
certification; it is never a skip-pass.

| Lane | State | Evidence |
| --- | --- | --- |
| Python unit + architecture with coverage | executed_passed | 8,533 passed in 2,122.70s; coverage 79% (`uv run pytest tests/unit tests/architecture -q --cov --cov-report=term`) |
| Focused V4-09 suite | executed_passed | 186 passed (`tests/unit/test_delegation_representation_*`, boundary, v4 invariants, docs, E2E) |
| V4/organization/formal-rule/dispute/evidence/representation regression selection | executed_passed | 1,825 passed, 6,713 deselected |
| Documentation parity | executed_passed | 44 passed across delegation, organization, formal-rule, dispute, evidence, operations docs suites |
| Ruff | executed_passed | `uv run ruff check src tests` — all checks passed |
| Mypy | executed_passed | `uv run mypy src tests` — no issues in 2,001 files |
| Import-linter | executed_passed | 25 contracts kept, 0 broken |
| Integration (`-m "integration and not scale"`) | unexecuted | 46 passed / 60 skipped; blocked on disposable PostgreSQL/pgvector and browser prerequisites |
| Integration including scale | unexecuted | Requires disposable PostgreSQL/pgvector and the 100,000-tick scale harness |
| Docker Compose config | executed_passed | `docker compose config --quiet` exit 0 |
| Compose/browser acceptance | unexecuted | Requires pinned API image, Playwright browser driver, and acceptance harness |
| Godot 4.7.2 regression | unexecuted | Godot binary/toolchain not installed |
| Benchmark/scale lane | unexecuted | Requires multi-hour 100,000-tick benchmark harness |
| Research UI tests | unexecuted | `pnpm` not installed |
| Research UI type/static checks | unexecuted | `pnpm` not installed |
| Research UI build | unexecuted | `pnpm` not installed |

Certification outcome: not certified — required Compose/browser, Godot, scale,
benchmark, and Research UI lanes are unexecuted with named prerequisites.

Task 24 audit: bundle integrity 24/24; 14 contexts / 12 flags / 3 owned flags;
`diplomacy` unowned; no `runner-config-v57`; six GET-only routes and six cursor
purposes; snapshot/store schemas present; catalog 160 with the three
representation families last; no representation command path or world-ledger
read; no `.ai-factory/ROADMAP.md` edit and branch remains `main`.

## Commit Plan

Proposed implementation checkpoints; no commit is made by planning.

1. After Tasks 1-3: `feat(v4): deepen the organizations representation contract`
2. After Tasks 4-6: `feat(v4): record owner-scoped representation mandates`
3. After Tasks 7-9: `feat(v4): recognize representation without legitimacy`
4. After Tasks 10-13: `feat(v4): analyze representation and speech alignment`
5. After Tasks 14-17: `feat(v4): publish delegation-representation-snapshot-v1`
6. After Tasks 18-19: `feat(v4): serve read-only representation surfaces`
7. After Tasks 20-24: `test(v4): enforce delegation-representation invariants`

## Blocking Conditions and Non-Goals

- Adding a new V4 flag, `runner-config-v57`, a new context, a runner root field,
  or a per-agent runner key to make this plan work is a blocking scope
  violation. Stop and re-plan.
- Claiming `diplomacy`, `organized_conflict`, or any other unowned V4 flag is
  forbidden. Representation is a prerequisite, not a substitute.
- Creating a RepresentationAuthority, LegitimacyOracle, TruthEngine, Verifier,
  Authenticator, RepresentativeRegistry, CoalitionRegistry, SettlementRegistry,
  polity, citizenship object, or binding mandate is forbidden.
- Letting `WorldEngine`, perception, admission, stop selectors, memory, prompts,
  observer semantics, or the Godot client read a representation ledger is
  forbidden.
- Letting a representation helper return, construct, submit, or resolve an
  `AgentCommand`, move a resource, or execute a physical action is forbidden.
- Treating recognized standing as permission, prohibition, legitimacy,
  authenticity, guilt, liability, or a binding finding is forbidden.
- Inferring a mandate, support, opposition, revocation, or conflict from silence,
  an unobserved act, or another owner's ledger is forbidden.
- Reading a peer owner's relationship, reputation, commitment, rule, office,
  institution, organization, decision, evidence, or representation ledger to
  evaluate representation is forbidden.
- Reconciling conflicting mandates into one authoritative representative is
  forbidden. Analysis may classify scope alignment for researchers only.
- Adding a new event, command, observer semantic type, write pair, artifact kind,
  record genre, `/v2` route, `observer-protocol-v2` serving, or SQL migration is
  forbidden.
- Rewriting the V3 mediation, collective-decision, structured-commitment,
  institution, office, durable-record, or V4 organization/formal-rule/dispute/
  evidence contracts is forbidden; representation is additive.
- Weakening an existing pin or assertion (catalog counts, Alembic `0017`,
  replay v22, codec v20, command count, observer semantic count, context count)
  is forbidden. The only intentional pin changes are 157 → 160 metric families,
  the addition of six representation routes alongside the existing route sets,
  and new representation snapshot/store schemas.
- Claiming prevalence, emergence probability, predictive power, accuracy,
  reliability of representatives in general, moral correctness, or a composite
  legitimacy score is forbidden.
- Editing `.ai-factory/ROADMAP.md` or closing M8 is out of scope;
  `$aif-roadmap` owns that.
- Changing the Godot client, observer protocol, observer capabilities, or
  `/version` is out of scope; the Research UI is the only client change.
- Enabling V4 flags in matrix lanes is out of scope; `experiments.matrix_schema`
  keeps its rejection gate.
- V4-09 does not add a command selector, prompt, or speech-generation bias.
  Recognition is a belief; a later plan that lets it bias behavior must be
  separately owned.
- Full qualification requires a disposable PostgreSQL/pgvector instance,
  Docker, a real browser driver, and the pinned Node/pnpm and Godot toolchains.
  A missing prerequisite leaves the lane unexecuted and blocks certification; it
  never becomes a skip-pass.
- Do not implement any other V4 context (`diplomacy`, `organized_conflict`,
  `infrastructure_networks`, `supply_chains`, `markets_credit`, `science`,
  `epidemics`, `ecological_feedback`, `disasters`, `societal_resilience`,
  `macro_society_identity`, or another organization/formal-rule/dispute/evidence
  extension) in this plan.

## Definition of Done

- All 24 indexed tasks have verified completion evidence; only this index holds
  task progress checkboxes.
- `organizations` remains the gate for representation; no `v57`, new flag,
  context, root field, or per-agent runner key exists; `diplomacy` stays unowned.
- The context registry validates at 14 contexts, 12 flags, and
  `v4-context-map-v2`; the analysis-only set and four reservations are unchanged.
- A general owner-scoped representation ledger exists with five closed principal
  kinds, closed scope and duration, mandatory provenance, support, opposition,
  revocation, conflicts, and derived recognition.
- Representation is never automatically legitimate: a self-claim alone is
  `claimed`; principal acts, independent support, or office/decision/written
  bases are required for `recognized`; rejection and contestation are retained.
- Same-root support never counts as independent, and the owner's self-support is
  excluded.
- A speaker cannot attribute a mandate to another party; forged or mismatched
  frames are dropped with a notice.
- Revocation is authorized and retained; unauthorized revocation attempts remain
  conflicts; expiry and supersession are explicit.
- Representation composes with collective decisions without duplicating
  proposal delegation, and exposes only a read-only summary for later diplomacy.
- Detached analysis keeps objective counts, owner rows, and analytical
  candidates separate with a hard leakage guard; researcher-only scope alignment
  never reaches agents.
- The metric catalog is exactly 160 with three appended families; the first 157
  are unchanged, and real completed-run assembly emits all three documents.
- No test file or current-pin doc line still asserts 157; the stale-pin guard
  passes, while historical revision statements and the first-154 digest pin are
  preserved.
- `delegation-representation-snapshot-v1` is canonical, bounded, immutable after
  publication; dispute, evidence, organization, and formal-rule snapshots remain
  decodable and byte-verifiable.
- Snapshot rows and API responses contain only hashed owner/principal/
  representative/actor tokens; no raw agent id or free-text scope subject is
  published.
- Public representation contracts are exported from `agents.cognition`,
  `analysis`, `experiments`, `simulation`, and `api.routes`; tests narrow shared
  `object` result fields before attribute access.
- Six GET-only `/v1` representation routes require `SUBJECTIVE_DEBUG`, have an
  explicit `representation_disabled` state, and are consumed by a read-only
  Research UI view.
- Cursor reuse works on every paged representation route; changed
  filter/run/publication/digest fails with 400 and expiry with 410.
- `WorldEngine` never reads a representation ledger; a socially rejected or
  contested representative does not block a physically possible command, and a
  physically impossible command is still rejected.
- The boundary suite proves owner-only authority, absence of legitimacy oracles,
  representative registries, command construction, peer-ledger reads, and
  world-ledger reads; no new commands/events/migrations are added; observer and
  migration pins are unchanged.
- The full V1-V4 regression lanes and static gates execute and pass; any
  unexecuted required lane is reported with its blocker and is not certified.
- Documentation states what representation controls (a belief), what it never
  controls (objective action, permission, or truth), how principals, scope,
  duration, support, opposition, revocation, conflicts, and frames work, how
  collective decisions compose, how diplomacy stays later, and every count
  matches the code.
- `docs/delegation-representation.md` is the canonical contract;
  `docs/analysis-metrics.md` documents the three families, `docs/research-ui.md`
  documents the panel, and README plus `docs/organizations.md` link the new
  contract.
