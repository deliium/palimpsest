<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-10 Diplomacy

Mode: ultra
Branch: main
Created: 2026-11-04
Plan identifier: `v4-10-diplomacy`

## Original Request

v4-10 inter society diplomacy

Naming requirement:

Use `v4-10-diplomacy`.

Implement long-running relationships between macro-society candidates and organizations using agent-mediated interaction.

Support:

- diplomatic contact

- envoys

- negotiations

- proposals

- promises

- agreements

- disputes

- shared projects

Do not create magical bilateral relationship scores between civilizations.

Macro-level relationship metrics must be derived from:

- agent relationships

- trade

- conflict

- agreements

- narratives

- institutional interaction

Representatives may misrepresent their society or lack full authority.

## Settings

- Testing: yes; full strategy. Unit, architecture, determinism, integration,
  Compose/browser, Godot regression, Research UI, benchmark regression, and
  static gates, with coverage enabled for Python lanes.
- Logging: verbose, metadata-only. Bounded DEBUG flow/counts, INFO milestones,
  WARN unresolved parties/truncation, ERROR safe codes. `PALIMPSEST_LOG_LEVEL`
  controls operational verbosity. Never log party references, envoy or actor
  identities, mandate ids, relation or instrument ids, scope subjects, agreement
  terms, support/opposition sets, revocation provenance, frame bodies, prompts,
  credentials, tokens, DSNs, memories, embeddings, utterance bodies, labels, or
  payload surrogates.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 25.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints are suggestions, not authorization to
  commit during planning.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-10-diplomacy`; the ultra bundle directory is
  `.ai-factory/plans/v4-10-diplomacy/`, phase files use `phase-NN-<slug>.md`,
  and `index.md` is the canonical entrypoint.
- Research source: `.ai-factory/RESEARCH.md` and `.ai-factory/research/` do not
  exist; no external research conclusions are invented.
- Execution: plan only. No implementation, commit, roadmap edit, or branch
  creation occurs in this invocation.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"
Rationale: V4-10 claims the declared, until now unowned `diplomacy` V4 context
on the accepted `runner-config-v56` seam, building long-running owner-scoped
relation records between organization, settlement, coalition, and agent parties
through existing speech, with retained termination rows, a closed scope/duration
matrix, current-standing derivation, analysis-only joins to `org-` and `msoc-`
candidates, and no bilateral score. The context already declares `organizations`
as its prerequisite (satisfied by V4-03/V4-04/V4-05) and `uses_existing_events:
true`, so no event, codec, command, observer semantic type, write pair, `/v2`
route, or migration is added. This plan does not edit or close the roadmap;
`$aif-roadmap` must register V4-10 in M8 and may reorder the "Next plans" list,
which currently names `infrastructure_networks` first.

## Requirements Reconciliation

Authority: the Original Request defines scope; `.ai-factory/ARCHITECTURE.md`
("Key Principles", "Capability ownership", "Important V3 seams", "Versioned
Extension Contract", V4-01 through V4-09 seams) and `.ai-factory/RULES.md`
constrain every edit; `.ai-factory/DESCRIPTION.md` and `.ai-factory/ROADMAP.md`
describe current state; completed V2/V3 contact, migration, commitment,
collective-project, mediation, office, institution, collective-decision, and
organization/operation/agency plus V4-03 through V4-09 code and
`tests/architecture/test_v4_architecture_invariants.py`,
`test_organization_*`, `test_formal_rule_boundaries`, `test_dispute_boundaries`,
`test_evidence_testimony_boundaries`, and
`test_delegation_representation_boundaries` govern compatibility. V4-10 claims
one existing flag and creates no context.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-10 owns `diplomacy`; no other V4 flag, `runner-config-v57`, new root field, per-agent runner key, or context is added | Original Request "inter society diplomacy"; `.ai-factory/ARCHITECTURE.md` "Capability ownership"; `src/simulation/v4_architecture.py` 150-163, 324-326; `src/simulation/runner_models.py` 305-325 | Task 2 tests; Task 22 pins; Task 26 `v57` absence |
| `diplomacy` is owner-scoped with owners `agents.cognition`, `social`, `simulation`, prerequisites `organizations`, and reuse of existing events | `src/simulation/v4_architecture.py` 150-163; `.ai-factory/ARCHITECTURE.md` "Important V3 seams" | Task 2/22 ownership audit |
| Registry prerequisites are planning-order declarations, not runtime gates: `diplomacy` runs with `organizations` off and leaves organization/coalition anchors unresolved | `src/simulation/v4_architecture.py` `prerequisite_contexts`; shipped `legal_disputes` without `formal_rules` (`tests/unit/test_dispute_config.py`) | Task 2/7 tests |
| Parties are closed to `agent`, `organization`, `settlement`, `coalition`, `unknown`; no polity, nation, civilization, border, or citizenship object | Original Request; `docs/v4-architecture.md` 133-138; `src/agents/cognition/delegation_representation.py` 92-99 | Task 1/4/22 tests |
| A relation is a retained record with an ordered party set that includes the owner's own self-party; every `relation_id` resolves inside the ledger | Original Request "long-running relationships"; `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts"; `src/agents/cognition/delegation_representation.py` 861-1017 | Task 4/10/16/22 tests |
| Termination, recall, resignation, expiry, and supersession append retained `DiplomaticTermination` rows; no row is deleted and no status is stored only at accreditation | Original Request; `.ai-factory/ARCHITECTURE.md` "Preserve append-only authoritative history" | Task 5/10/22 tests |
| Organization and coalition anchors resolve only against the owner's own `orgc-` concepts; settlement anchors only against owner-visible region context; missing anchors stay unresolved | `src/agents/cognition/organization_concepts.py` 31, 373; `src/world/observations.py` 333-374; `.ai-factory/ARCHITECTURE.md` V4-03 seam | Task 7/12 tests |
| Scope coverage is one closed matrix over mandate `scope_kind`/`duration_kind` and instrument kind; a `single_act`/`occasion` mandate cannot recognize a long-running agreement and a named scope subject must match the instrument subject | Original Request "Representatives may lack full authority"; `src/agents/cognition/delegation_representation.py` 102-133, 477-506 | Task 1/9/14/22 tests |
| `msoc-` and `org-` identities are analysis-only and are never passed to cognition; diplomacy analysis joins party tokens to them read-only | `.ai-factory/ARCHITECTURE.md` "analysis is read-only"; `src/analysis/macro_society_contract.py` 59, 241; `src/analysis/organization_contract.py` 175-200 | Task 12/13/22 tests |
| A long-running relation is a retained record plus episodes and declarations; the ledger stores no valence, rank, score, or composite | Original Request "Do not create magical bilateral relationship scores" | Task 4/12/15/22 tests |
| Envoys derive standing from the owner's representation ledger; absence, `claimed`, `contested`, `rejected`, `revoked`, `expired`, and `superseded` are all legal | Original Request "lack full authority"; `src/agents/cognition/delegation_representation.py` 124-191 | Task 9/23 tests |
| Current envoy standing is recomputed at detection, export, and compose time; the stored envoy status is only the accreditation-time snapshot | `src/agents/cognition/delegation_representation.py` 124-134, 1305-1315 | Task 7/9/18/22 tests |
| An agreement is `apparently_accepted` only with at least two distinct parties' own declarations; a principal's own declaration counts directly, an envoy's declaration requires recognized standing, and an envoy's say-so never binds | Original Request; `src/agents/cognition/legal_disputes.py` resolution rules; `.ai-factory/ARCHITECTURE.md` V4-07 seam | Task 9/23 tests |
| Misrepresentation is a retained observation with four closed kinds; no lie, truth, guilt, or bad-faith field exists | Original Request "Representatives may misrepresent their society" | Task 5/9/22 tests |
| Promises reference commitments as opaque anchors and are never enforced; disputes link owner dispute/evidence rows; shared projects link collective-project/agency rows | `.ai-factory/ARCHITECTURE.md` V3-17/V3-20/V3-31 seams | Task 8/22 tests |
| Contact evidence comes from observed `contact_recorded` co-presence or communicated claims; third-party reports never resolve a party | `src/world/_perception.py` 1119-1126; `src/world/observations.py` 973-1019 | Task 6/7/23 tests |
| Speech is the only claim channel: bounded `dip_v1` frames travel in existing `Talk`/`Ask`/`Tell`, and a verified speaker must match the claimed envoy | `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts"; `src/agents/cognition/delegation_representation_communication.py` 57-62 | Task 6/22 tests |
| The owner's ledger reaches `Perspective` and `SimulationRunnerResult` through the V4-09 carry path; the result document is unchanged | `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime"; `src/simulation/perception.py` 143-163; `src/simulation/runner_models.py` 6380-6735 | Task 11 tests; Task 22 carry scan |
| Detached analysis keeps objective counts, owner-token rows, and analytical candidates in three separate types with a hard leakage guard | `.ai-factory/ARCHITECTURE.md` Key Principle 1; `src/analysis/delegation_representation_layers.py` | Task 14/22 tests |
| Macro-level relation metrics derive from six independent lanes and contain no composite or bilateral score key | Original Request lane list; `src/analysis/specifications.py` 312-355 | Task 12/15/22 tests |
| Researcher-only envoy alignment (`consistent`, `unresolved`, `inconsistent`, `not_applicable`) never reaches cognition, prompts, memory, world state, stop selectors, or observer semantics | Original Request; `.ai-factory/ARCHITECTURE.md` "analysis is read-only" | Task 14/22 tests |
| Derived rows are materialized by one ordered update pipeline (append -> derive -> detect misrepresentation -> expire -> supersede -> detect conflicts -> enforce limits) with content-addressed dedupe | `.ai-factory/ARCHITECTURE.md` "analysis is read-only" and owner-scoped beliefs; `src/agents/cognition/delegation_representation.py` 1497-1505, 2151-2158 | Task 7/10/11/22 tests |
| Token domains interoperate with V4-09: owner/envoy/actor/agent-party tokens share one agent-identity domain, while `orgc-` and region anchors stay owner-safe for `org-`/`msoc-` joins | `src/analysis/delegation_representation_contract.py` 166-191; `src/analysis/organization_contract.py` 175-200; `src/analysis/macro_society_contract.py` 241 | Task 12/13/14/16/22 tests |
| The trade lane counts `ExchangeCompleted` only; one-way `Given` transfers are never labelled trade | Original Request "trade"; `src/analysis/exchange_functions.py` 79-120; `src/world/events.py` 617 | Task 12/23 tests |
| The catalog grows 160 -> 164 by appending four families; the first 160 keep id, order, version, and value keys | `src/analysis/specifications.py` 53, 7376 | Task 15/22/25 pin checks |
| Raising the catalog sweeps every hard-coded current pin in tests and docs to 164; historical revision statements and the first-154 digest stay unchanged | `src/analysis/specifications.py:53`; 49 test files with 78 `== 160` occurrences; current doc lines `docs/analysis-metrics.md:41`, `docs/architecture.md` 565/596/659, `docs/disputes.md:225`, `docs/evidence-testimony.md:211`, `docs/delegation-representation.md:137`, `.ai-factory/ARCHITECTURE.md` 184/844-845, `.ai-factory/DESCRIPTION.md` 385/390 | Task 15 sweep and guard; Task 25 re-run |
| The four-owned/eight-unowned ownership pin sweeps every test and doc statement, including `test_formal_rule_regression.py`, `test_formal_rule_docs.py`, `test_dispute_docs.py`, `test_organization_docs.py`, `test_organization_operations_docs.py`, and `test_evidence_testimony_docs.py` | `src/simulation/runner_models.py` 320-325; `src/simulation/compatibility.py` 155-157; `docs/architecture.md` 565-567/660; `docs/configuration.md` 310-312; `docs/research-api.md:88`; `.ai-factory/ARCHITECTURE.md` 205/768-769/813-814/847-848 | Task 2/25/26 tests |
| Snapshot and API rows expose hashed owner/party/envoy/actor tokens and owner-safe `orgc-`/region anchors only; no raw agent id, free-text subject, or frame body is published | `.ai-factory/ARCHITECTURE.md` Key Principle 5; `src/analysis/delegation_representation_contract.py` token pattern | Task 12/16/20/22 tests |
| `diplomacy-snapshot-v1` is independent; organization, formal-rule, dispute, evidence, and representation snapshots remain byte-verifiable | `.ai-factory/ARCHITECTURE.md` "Use accepted-set and exact-key-set schema evolution"; `src/simulation/evidence_testimony_codec.py` 344-488 | Task 16/22/26 snapshot tests |
| Simulation snapshot rows use `DiplomacySnapshot*Row` names (mirroring `DelegationRepresentation*Row`) so they never collide with analysis `Diplomacy*Row` types; publication ids mirror the two-argument content-addressed precedent | `src/simulation/delegation_representation_models.py` 177-379; `src/simulation/delegation_representation_codec.py` 199-207; `src/analysis/delegation_representation_rows.py` 64-152 | Task 16/18/22 tests |
| Access is six GET-only `/v1/simulations/{run_id}/diplomacy...` routes requiring `SUBJECTIVE_DEBUG`, with `diplomacy_disabled` when unconfigured and 404 for an unknown published relation/instrument | `docs/research-api.md`; `src/api/routes/delegation_representation.py` | Task 20/22 route tests; Task 23 API reads |
| Cursors bind run, publication, digest, purpose, and filters; mismatch is 400 and expiry is 410 | `src/simulation/delegation_representation_ports.py` 39-164; `src/api/delegation_representation_cursor.py` | Task 17/20/23 tests |
| Publication is opt-in, post-completion, atomic, quota-bounded, and isolated from scientific status | `src/experiments/evidence_testimony_publication.py` 57-341; `src/persistence/evidence_testimony_filesystem.py` 52-327 | Task 18/19/23 tests |
| The end-to-end scenario runs in-process in the focused/unit lane, uses real admission/speech/recognition/publication/routes, and is never reported as an integration-only or PostgreSQL prerequisite | `.ai-factory/ARCHITECTURE.md` V3/V4 seams; `pyproject.toml` 99-113; `tests/integration/test_delegation_representation_e2e.py` | Task 23/24 tests |
| No SQL migration, new event, command, observer semantic type, write pair, `/v2` route, or `observer-protocol-v2` is added | `.ai-factory/ARCHITECTURE.md` requirements 4-6; `src/simulation/versioning.py` 39-90 | Task 22/26 pins |
| Diplomacy rows flow through `MetricComputationInputs`, `experiments.collectors`, and `analysis.metric_service`; real completed-run assembly emits all four families | `.ai-factory/ARCHITECTURE.md` "analysis is read-only"; `src/analysis/metric_service.py` 218-340, 408; `src/experiments/collectors.py` 620-890 | Task 15 tests; Task 23 assembly |
| Required lanes must execute; a missing prerequisite is reported `unexecuted` with a prerequisite, never as a skip-pass | Plan Settings; `docs/development.md`; `tests/compose/acceptance.py` | Task 24 receipt; Task 26 audit |
| The roadmap is owned by `$aif-roadmap` and is not edited here | `.ai-factory/ARCHITECTURE.md` requirement 7 | Task 25/26 `git status` |

### Supported combinations and availability transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| Default runner config, all V4 flags off | V4-09-equivalent behavior | No diplomacy ledger, metric, publication, or route data | Task 3/11/23 flags-off tests |
| `diplomacy` enabled on v4 or v55 | Unchanged config | `v4_capability_requires_v56` before construction | Task 2 test |
| `diplomacy` enabled on v56 | Valid run | Diplomacy mode DETERMINISTIC; ledger active | Task 3/11 test |
| `organizations` enabled alone | Valid run | No diplomacy ledger | Task 3 test |
| `formal_rules` or `legal_disputes` alone | Valid run | Diplomacy stays DISABLED | Task 3 test |
| `diplomacy` enabled with `organizations` off | Valid run | Agent/settlement parties work; organization/coalition claims stay unresolved | Task 2/7 test |
| `organized_conflict` or any other unowned flag | No behavior change | Still fails closed with `capability_unimplemented` | Task 2/22 test |
| Direct `contact_recorded` co-presence | Contact episode | `direct_co_presence`; relation record with self-party and counterparty; no authority | Task 4/7 test |
| Mediated `dip_contact` frame | Contact episode | `mediated_message`; party resolution from the owner's anchors | Task 7/23 test |
| New relation or party | Retained relation row | Ordered `party_ids` include the owner self-party; no invented collective | Task 4/10 test |
| Third-party report of contact | Report only | `third_party_report`; counterparty never marked accepted | Task 7 test |
| Organization party with owned `orgc-` concept | Resolved party | Anchor resolves; envoy standing still independent | Task 7 test |
| Organization party without an owned concept | Unresolved party | `resolution=unresolved`; no invented collective | Task 7 test |
| Settlement party with visible region context | Resolved party | Region anchor retained | Task 7 test |
| Settlement party with no visible region | Unresolved party | `resolution=unresolved`; no invented place | Task 7 test |
| Envoy self-claim with no mandate | Owner belief | `envoy_status=claimed`; authority-bearing declaration yields `mandate_unrecognized` | Task 9 test |
| Envoy with recognized mandate and covering scope | Recognized standing | Declaration counts for its party | Task 9/23 test |
| Envoy with `contested`/`rejected`/`revoked`/`expired` mandate | Non-recognized standing | Declaration retained as communicated; misrepresentation row | Task 9 test |
| Earlier mandate status was `recognized`, later `superseded` | Current standing | Recomputed `superseded`; stored accreditation status is not treated as current | Task 7/9 test |
| Mandate scope cannot cover the instrument kind | Scope mismatch | `scope_exceeded` retained; declaration retained | Task 9 test |
| Mandate duration is `single_act`/`occasion` and the instrument is long-running | Scope mismatch | `scope_exceeded`; declaration retained | Task 9 test |
| Principal's later declaration contradicts an envoy | Contradiction | `contradicted_by_principal`; principal governs the party | Task 9/23 test |
| Principal declares acceptance with no envoy | Principal act | Counts directly for its party; no mandate required | Task 9/23 test |
| Member contests an envoy | Contest | `contested_by_member`; no deletion | Task 9 test |
| Proposal with opener only | Proposed | `proposed` / `opener_only` | Task 9 test |
| One party accepts a two-party proposal | Still proposed | Not `apparently_accepted` | Task 9/23 test |
| Each party's principal or recognized envoy accepts | Apparently accepted | `apparently_accepted` / `all_parties_declared`; binds nobody | Task 9/23 test |
| Any active reject | Rejected | `rejected`; retained | Task 9 test |
| Opener withdraws | Withdrawn | `withdrawn` / `withdrawn` | Task 10 test |
| Active dispute on an instrument | Unresolved | `unresolved` / `disputed` | Task 10 test |
| Promise declaration | Open promise | `open`; never fulfilled or broken by the system | Task 8/9 test |
| Promise completion claim | Claimed completion | `completed_claimed`; no objective verification | Task 9 test |
| Shared project with every party accepted | Active belief | `active`; no work performed or resource allocated | Task 9 test |
| Shared project completion claim | Claimed completion | `completed_claimed`; no objective check | Task 9 test |
| `end_tick` boundary | Expiry | `expired` when `tick >= end_tick`; rows retained | Task 10 test |
| Later recognized instrument on the same subject | Supersession | Older `superseded` plus a retained termination row; two recognized agreements may coexist | Task 10 test |
| Envoy recalled or resigned | Termination | Retained `DiplomaticTermination`; no row deleted | Task 5/10 test |
| Duplicate envoy/contradictory terms/conflicting party/agreement dispute | Conflict | Retained conflict rows; never reconciled | Task 10 test |
| Trade evidence from one-way `Given` | Transfer only | No trade-lane row; `exchange_count` stays zero | Task 12 test |
| Trade evidence from `ExchangeCompleted` | Trade lane | One trade-lane row per completed exchange | Task 12/23 test |
| Cap exceeded with droppable rows | Truncation | `diplomacy_truncated`; deterministic drop | Task 10/16 test |
| Cap exceeded with nothing droppable | Capacity error | `diplomacy_capacity_reached` | Task 10 test |
| Snapshot exceeds 4 MiB or row caps | No publication | `diplomacy_size_limit` | Task 16/18 test |
| Duplicate publication id with different bytes | Existing artifact untouched | `diplomacy_publication_exists` | Task 18 test |
| `PALIMPSEST_DIPLOMACY_ROOT` unset | API state unset | 503 `diplomacy_disabled`; CLI receipt `disabled` | Task 19/20/23 tests |
| Cursor reused with same run/publication/digest/purpose/filters | Same page | 200; digest matches | Task 17/20 test |
| Cursor reused after any binding change | No page served | 400 `diplomacy_cursor_invalid`; expired 410 | Task 17/20 test |
| Run incomplete or publication failed | Scientific result unchanged | Receipt `unavailable`/`failed` only | Task 18/23 test |
| In-process diplomacy E2E without PostgreSQL | No integration prerequisite | Runs in the focused/unit lane with real ticks, speech, recognition, publication, and routes | Task 23/24 test |
| Required Compose/browser/Godot/benchmark/UI lane with a missing prerequisite | No green certification | Recorded `unexecuted` with prerequisite | Task 24/26 |

No blocking open questions: every material decision is fixed below.

## Architecture and Decisions

1. **One owned flag, one new ownership claim.** V4-10 claims `diplomacy` and adds
   no V4 flag, context, `runner-config-v57`, runner root field, or per-agent
   runner key. Activation is `runner-config-v56` +
   `v4_capability_flags.diplomacy`.
2. **Prerequisites are planning order.** The registry's
   `DIPLOMACY.prerequisite_contexts = (ORGANIZATIONS,)` orders the work; it is
   not a new runtime gate. With `organizations` off, organization and coalition
   party anchors stay unresolved. This matches the shipped `legal_disputes`
   behavior without `formal_rules`.
3. **Parties are representation principals.** `agent`, `organization`,
   `settlement`, `coalition`, and `unknown` are the only kinds. Every relation
   carries an ordered party set that includes the owner's own self-party; no
   polity, nation, civilization, border, citizenship, tribe, or state object
   exists.
4. **Macro identities stay analytical.** Cognition never receives `msoc-` or
   `org-` ids. Analysis joins hashed party tokens to those identities read-only;
   it never mints, renames, splits, merges, or dissolves one.
5. **Relations are retained records, not scores.** A `DiplomaticRelation` row
   owns the ordered party set and groups contacts, envoys, negotiations,
   instruments, declarations, and terminations. The ledger stores no valence,
   rank, trust value, index, or composite.
6. **No bilateral score anywhere.** Macro-level relation evidence is per-lane
   counts with explicit denominators; the lane family has no aggregate key.
7. **Envoys are mandates, not authority.** Standing derives from the owner's
   representation ledger. Absent, claimed, contested, rejected, revoked,
   expired, and superseded standing are all legal and all retained. Current
   standing is recomputed at detection, export, and compose time; the stored
   envoy status is only the accreditation-time snapshot.
8. **Misrepresentation is observation, not adjudication.** Four kinds are
   retained; there is no lie detector, truth field, guilt, bad faith, or
   punishment.
9. **Agreement needs every party's own declaration.** A principal's own
   declaration counts directly for its party; an envoy's declaration requires
   recognized standing and never binds a party. `apparently_accepted` still
   binds nobody.
10. **Promises are declarations.** They reference commitments as opaque anchors
    and are never enforced or objectively verified.
11. **Disputes and shared projects compose read-only.** They cite the owner's
    dispute, evidence, collective-project, and organization-agency rows; no
    court, project executor, or resource allocation exists.
12. **Contact is observed co-presence or a communicated claim.** A third-party
    report is recorded as a report and resolves nothing.
13. **Speech is the only claim channel.** Bounded `dip_v1` frames travel in
    existing `Talk`/`Ask`/`Tell`; the verified speaker must be the claimed envoy.
14. **Termination is explicit and retained.** Withdrawal, recall, resignation,
    dispute, expiry, and supersession append a `DiplomaticTermination` row;
    nothing is deleted and no status lives only on an accreditation row.
15. **Conflicts coexist.** Duplicate envoys, contradictory terms, conflicting
    parties, and agreement disputes stay unresolved; two recognized agreements
    may coexist.
16. **No command path.** No diplomacy helper constructs, submits, resolves, or
    executes an `AgentCommand`; every physical effect remains ordinary admission.
17. **Composition, not duplication.** Representation, decisions, commitments,
    offices, rules, disputes, and evidence are consulted read-only.
18. **Three layers, three types.** Objective counts, owner-token rows, and
    analytical candidates are separate; leakage is a hard failure.
19. **No objective alignment in cognition.** `consistent`, `unresolved`,
    `inconsistent`, and `not_applicable` exist only in detached analysis.
20. **A new snapshot, not a rewrite.** `diplomacy-snapshot-v1` is independent;
    all existing snapshots remain decodable and byte-verifiable.
21. **Metrics append only.** 160 -> 164. The first 160 keep id, order, version,
    and value keys.
22. **Deterministic by construction.** Sorted ordering, content-addressed ids,
    canonical JSON digests, quantized ratios, integer counts, no `hash()`, no
    UUID, and no wall-clock domain values.
23. **Read-only surfaces.** Six GET routes under `/v1` require
    `SUBJECTIVE_DEBUG`; the Research UI derives no authority, legitimacy, score,
    or winner.
24. **Cursors bind to the publication digest.** Every paged route binds run,
    publication, digest, purpose, and filters.
25. **Publication is opt-in and non-interfering.** A storage or composition
    failure changes only the receipt, never the scientific result.
26. **No automatic generalization.** V4-10 implements no organized conflict,
    infrastructure, supply chain, market, credit, science, epidemic, ecological,
    disaster, resilience, or macro-society behavior.
27. **Published identities are tokens.** Hashed owner/party/envoy/actor tokens
    and owner-safe `orgc-`/region anchors only; raw agent ids, free-text
    subjects, and frame bodies never leave the owner's private ledger.
28. **Scope coverage is one closed matrix.** A mandate's `scope_kind` and
    `duration_kind` decide whether it covers an instrument kind; `single_act`
    and `occasion` never recognize a long-running agreement, and a named scope
    subject must match the instrument subject. `SCOPE_EXCEEDED` and researcher
    alignment consume the same helper.
29. **Derived rows have one pipeline.** The update appends raw rows, derives
    current standings, detects misrepresentation, expires, supersedes, detects
    conflicts, and enforces caps in that order. Detection rows are
    content-addressed and deduplicated, so repeating an update never duplicates
    them.
30. **Token domains interoperate with V4-09.** Owner, envoy, actor, and
    agent-party tokens share one agent-identity domain (documented as an
    intentional alias if V4-09 keeps owner/principal domains distinct);
    `orgc-` and region anchors stay owner-safe so `org-`/`msoc-` joins and
    representation alignment resolve.
31. **Pin sweeps distinguish current from historical.** Current pins move to 164
    and four owned/eight unowned; historical revision statements keep their
    original numbers. The stale-pin guard scans current-count assertions rather
    than rewriting history.

### Context declaration

| Context | Flag | Authority | Owning packages | Prerequisites | Existing mechanism | Event strategy |
| --- | --- | --- | --- | --- | --- | --- |
| `diplomacy` (newly owned) | `diplomacy` (owned by V4-10) | owner-scoped | `agents.cognition`, `social`, `simulation` | `organizations` (planning order, not a runtime gate) | contact, migration, commitments, representation, collective decisions, organizations, offices, formal rules, disputes, evidence | reuse |

Supporting packages without authority: `analysis` (detached rows, candidates,
lanes, metrics), `experiments` (harvest/publication bridge), `persistence`
(filesystem store), `api` (read-only routes), `research_runner` (opt-in CLI
producer), and the Research UI client.

### Compatibility pins

Default runner/result `v4`/`v2`; latest feature runner `v55`; accepted runner adds
`v56` only; events `EVENT_SCHEMA_REPLAY_V22` (22); codec `v20`; commands 43;
observer semantic types 73; metric families **164 (V4-10 change)**; Alembic
`0017` with no `0018`; `/v1`; `observer-protocol-v1`; observer layout
`observer-layout-v1`; observer capabilities 4 advertised / 6 reserved; four
reserved write pairs (events 23-26 / codecs `v21`-`v24`); `prepare_parallel=False`;
six GET organization, six GET formal-rule, six GET dispute, six GET evidence, six
GET representation, and six GET diplomacy routes; six cursor purposes per
context; snapshots `organization-snapshot-v1`/`v2`/`v3`,
`formal-rule-snapshot-v1`, `dispute-resolution-snapshot-v1`,
`evidence-testimony-snapshot-v1`,
`delegation-representation-snapshot-v1`, and `diplomacy-snapshot-v1`; stores
`organization-store-v1`, `formal-rule-store-v1`,
`dispute-resolution-store-v1`, `evidence-testimony-store-v1`,
`delegation-representation-store-v1`, and `diplomacy-store-v1`; 14 V4 contexts /
12 flags / **4 owned flags** (`organizations`, `formal_rules`,
`legal_disputes`, `diplomacy`) / **8 unowned** (`organized_conflict`,
`infrastructure_networks`, `supply_chains`, `markets_credit`, `science`,
`epidemics`, `ecological_feedback`, `disasters`). The other capability sets
still hold `institutional_economy` and `multi_hop_testimony_tracking` unowned;
they are not part of the 12 V4 flags. `/version` is unchanged;
`organization_rows` remains reserved.

## Phase Index

1. [Phase 1: Contract and Seam](phase-01-contract-and-seam.md) — Tasks 1-3
2. [Phase 2: Owner-Scoped Diplomacy Beliefs](phase-02-diplomacy-beliefs.md) — Tasks 4-11
3. [Phase 3: Detached Analysis, Candidates, and Metrics](phase-03-detached-analysis.md) — Tasks 12-15
4. [Phase 4: Diplomacy Snapshot v1](phase-04-snapshot-v1.md) — Tasks 16-17
5. [Phase 5: Composition and Durable Publication](phase-05-composition-publication.md) — Tasks 18-19
6. [Phase 6: Read-Only API and Research UI](phase-06-read-only-surfaces.md) — Tasks 20-21
7. [Phase 7: Invariants, End-to-End Diplomacy, and Regression](phase-07-invariants-and-regression.md) — Tasks 22-24
8. [Phase 8: Documentation and Final Verification](phase-08-docs-and-verification.md) — Tasks 25-26

## Cross-Phase Dependencies

- All phases assume the completed V2/V3 contact, migration, commitment,
  collective-project, mediation, office, institution, collective-decision, and
  organization stacks plus V4-01 through V4-09; V4-10 does not rewrite them, but
  Tasks 22/24 must keep their suites green.
- Task 2 depends on Task 1: the ownership pin uses the frozen vocabulary.
- Task 3 depends on Task 2: the mode and policy reference the owned flag.
- Task 4 depends on Task 3: records use the policy, ids, and caps.
- Task 5 depends on Task 4: termination and declaration rows extend the same
  ledger, relation references, and party set introduced by Task 4.
- Task 6 depends on Tasks 4-5: `dip_v1` frames encode the record vocabulary,
  including `topic_subject`.
- Task 7 depends on Tasks 4-6: contact/envoy/negotiation collection consumes
  frames and anchors, but leaves cap enforcement to Task 10.
- Task 8 depends on Tasks 4-7: instruments and declarations consume relation,
  envoy, and party rows.
- Task 9 depends on Tasks 7-8: standing, acceptance, and misrepresentation
  consume envoys, instruments, declarations, and representation.
- Task 10 depends on Tasks 7-9: the ordered update pipeline appends termination,
  expiry, supersession, conflict, and truncation rows over every row type; it
  also owns cap enforcement so Task 7 never forward-references it.
- Task 11 depends on Tasks 4-10: runtime carry needs the complete ledger.
- Task 12 depends on Task 11: harvest reads exported ledgers and lane inputs.
- Task 13 depends on Task 12: candidates consume harvested rows and lane rows.
- Task 14 depends on Tasks 12-13: layers and alignment consume rows, candidates,
  and identity joins.
- Task 15 depends on Tasks 12-14: the four families read rows, lanes, layers, and
  alignment.
- Task 16 depends on Tasks 9 and 12-15: the snapshot mirrors derived current
  standings, rows/counts/lineage, and metric provenance.
- Task 17 depends on Task 16: paging and ports select typed snapshot rows.
- Task 18 depends on Tasks 9, 10, 15, and 17: the composer derives current
  statuses, termination views, analysis, and ports at publication time.
- Task 19 depends on Tasks 16-18: the store serves snapshots and pages, and the
  CLI producer calls the Task 18 composer.
- Task 20 depends on Task 19: the API reads the committed store.
- Task 21 depends on Task 20: the panel consumes the six routes.
- Task 22 depends on Tasks 2-21: the suite asserts every authority claim.
- Task 23 depends on Tasks 7-21: the E2E uses real ticks, speech, recognition,
  publication, and routes.
- Task 24 depends on Tasks 22-23: regression runs after the invariant/E2E gates.
- Task 25 depends on Tasks 2-24: documentation describes verified surfaces.
- Task 26 depends on Tasks 24-25: final certification needs receipts and docs.

## Tasks

### Phase 1: Contract and Seam
- [x] Task 1: Freeze the diplomacy vocabulary, party grammar, and locked policy ([details](phase-01-contract-and-seam.md#task-1-freeze-the-diplomacy-vocabulary-party-grammar-and-locked-policy))
- [x] Task 2: Own the diplomacy flag on the runner-config-v56 seam ([details](phase-01-contract-and-seam.md#task-2-own-the-diplomacy-flag-on-the-runner-config-v56-seam)) (depends on 1)
- [x] Task 3: Add the cognition diplomacy mode and policy seam ([details](phase-01-contract-and-seam.md#task-3-add-the-cognition-diplomacy-mode-and-policy-seam)) (depends on 2)

### Phase 2: Owner-Scoped Diplomacy Beliefs
- [x] Task 4: Define relation, party, contact, envoy, and negotiation records ([details](phase-02-diplomacy-beliefs.md#task-4-define-relation-party-contact-envoy-and-negotiation-records)) (depends on 3)
- [x] Task 5: Define instrument, declaration, misrepresentation, termination, and conflict records ([details](phase-02-diplomacy-beliefs.md#task-5-define-instrument-declaration-misrepresentation-termination-and-conflict-records)) (depends on 4)
- [x] Task 6: Add bounded dip_v1 diplomacy speech frames ([details](phase-02-diplomacy-beliefs.md#task-6-add-bounded-dip_v1-diplomacy-speech-frames)) (depends on 4, 5)
- [x] Task 7: Collect contacts, envoys, and negotiations ([details](phase-02-diplomacy-beliefs.md#task-7-collect-contacts-envoys-and-negotiations)) (depends on 4-6)
- [x] Task 8: Collect proposals, promises, agreements, disputes, and shared projects ([details](phase-02-diplomacy-beliefs.md#task-8-collect-proposals-promises-agreements-disputes-and-shared-projects)) (depends on 4-7)
- [x] Task 9: Derive envoy standing, agreement acceptance, and misrepresentation ([details](phase-02-diplomacy-beliefs.md#task-9-derive-envoy-standing-agreement-acceptance-and-misrepresentation)) (depends on 7, 8)
- [x] Task 10: Retain termination, supersession, expiry, and conflicts ([details](phase-02-diplomacy-beliefs.md#task-10-retain-termination-supersession-expiry-and-conflicts)) (depends on 7-9)
- [x] Task 11: Carry the diplomacy ledger through cognition and runtime ([details](phase-02-diplomacy-beliefs.md#task-11-carry-the-diplomacy-ledger-through-cognition-and-runtime)) (depends on 4-10)

### Phase 3: Detached Analysis, Candidates, and Metrics
- [x] Task 12: Harvest diplomacy rows and six inter-society evidence lanes ([details](phase-03-detached-analysis.md#task-12-harvest-diplomacy-rows-and-six-inter-society-evidence-lanes)) (depends on 11)
- [x] Task 13: Detect relation candidates, join candidate identities, and derive forward-only lineage ([details](phase-03-detached-analysis.md#task-13-detect-relation-candidates-join-candidate-identities-and-derive-forward-only-lineage)) (depends on 12)
- [x] Task 14: Project three layers and researcher-only envoy alignment ([details](phase-03-detached-analysis.md#task-14-project-three-layers-and-researcher-only-envoy-alignment)) (depends on 12, 13)
- [x] Task 15: Add four metric families and raise the catalog to 164 ([details](phase-03-detached-analysis.md#task-15-add-four-metric-families-and-raise-the-catalog-to-164)) (depends on 12-14)

### Phase 4: Diplomacy Snapshot v1
- [x] Task 16: Define diplomacy-snapshot-v1 and its codec ([details](phase-04-snapshot-v1.md#task-16-define-diplomacy-snapshot-v1-and-its-codec)) (depends on 9, 12-15)
- [x] Task 17: Add paging, read ports, and cursor support ([details](phase-04-snapshot-v1.md#task-17-add-paging-read-ports-and-cursor-support)) (depends on 16)

### Phase 5: Composition and Durable Publication
- [x] Task 18: Compose completed-run snapshots and receipts ([details](phase-05-composition-publication.md#task-18-compose-completed-run-snapshots-and-receipts)) (depends on 9, 10, 15, 17)
- [x] Task 19: Add the atomic filesystem store and CLI producer ([details](phase-05-composition-publication.md#task-19-add-the-atomic-filesystem-store-and-cli-producer)) (depends on 16-18)

### Phase 6: Read-Only API and Research UI
- [x] Task 20: Add six GET routes, schemas, settings, and app wiring ([details](phase-06-read-only-surfaces.md#task-20-add-six-get-routes-schemas-settings-and-app-wiring)) (depends on 19)
- [x] Task 21: Add the read-only Research UI diplomacy view ([details](phase-06-read-only-surfaces.md#task-21-add-the-read-only-research-ui-diplomacy-view)) (depends on 20)

### Phase 7: Invariants, End-to-End Diplomacy, and Regression
- [x] Task 22: Add the diplomacy boundary and determinism suite ([details](phase-07-invariants-and-regression.md#task-22-add-the-diplomacy-boundary-and-determinism-suite)) (depends on 2-21)
- [x] Task 23: Add the diplomacy end-to-end scenario ([details](phase-07-invariants-and-regression.md#task-23-add-the-diplomacy-end-to-end-scenario)) (depends on 7-21)
- [x] Task 24: Execute the full V1-V4 regression and qualification lanes ([details](phase-07-invariants-and-regression.md#task-24-execute-the-full-v1-v4-regression-and-qualification-lanes)) (depends on 22, 23)

### Phase 8: Documentation and Final Verification
- [x] Task 25: Execute the documentation checkpoint ([details](phase-08-docs-and-verification.md#task-25-execute-the-documentation-checkpoint)) (depends on 2-24)
- [x] Task 26: Perform final V4-10 verification ([details](phase-08-docs-and-verification.md#task-26-perform-final-v4-10-verification)) (depends on 24, 25)

## Verification Receipt (Tasks 24 and 26)

To be completed by Task 24 and audited by Task 26. Every required lane must be
recorded as exactly one of `executed_passed`, `executed_failed`, or
`unexecuted`. An `unexecuted` lane carries its missing prerequisite and blocks
certification; it is never a skip-pass. Initial planning state is `unexecuted`
for every lane because nothing has run yet.

| Lane | State | Evidence |
| --- | --- | --- |
| Python unit + architecture with coverage | executed_passed | `uv run pytest tests/unit tests/architecture -q --cov --cov-report=term`: 8,791 passed, 79% total coverage (2026-11-04/05) |
| Focused V4-10 suite | executed_passed | `uv run pytest tests/unit/test_diplomacy_*.py tests/architecture/test_diplomacy_boundaries.py -q`: 253 passed |
| Focused in-process diplomacy E2E | executed_passed | `uv run pytest tests/unit/test_diplomacy_e2e.py -q`: 2 passed (no PostgreSQL) |
| V4/organization/formal-rule/dispute/evidence/representation/diplomacy regression selection | executed_passed | Covered by the 8,791-test unit+architecture lane; focused V4-10 suite 253 passed |
| Documentation parity | executed_passed | `tests/unit/test_diplomacy_docs.py` plus the existing docs/catalog parity tests pass; four-owned/eight-unowned and 164 pins swept |
| Ruff | executed_passed | `uv run ruff check src tests`: all checks passed |
| Mypy | executed_passed | `uv run mypy src tests`: no issues in 2,050 files |
| Import-linter | executed_passed | `uv run lint-imports`: 25 kept, 0 broken |
| Integration (`-m "integration and not scale"`) | unexecuted | Requires a disposable PostgreSQL/pgvector instance (not available in this session) |
| Integration including scale | unexecuted | Requires a disposable PostgreSQL/pgvector instance and the 100,000-tick harness |
| Docker Compose config | executed_passed | `docker compose config --quiet`: passed |
| Compose/browser acceptance | unexecuted | Requires the pinned API image, Playwright driver, and acceptance harness |
| Godot 4.7.2 regression | unexecuted | Requires the Godot binary/toolchain (not installed) |
| Benchmark/scale lane | unexecuted | Requires the multi-hour 100,000-tick harness |
| Research UI tests | unexecuted | Requires `pnpm` (not installed) |
| Research UI type/static checks | unexecuted | Requires `pnpm` (not installed) |
| Research UI build | unexecuted | Requires `pnpm` (not installed) |

Certification outcome: **not certified** — every Python, static, docs, and Compose-config lane passed, but integration, Compose/browser, Godot, benchmark, and Research UI lanes remain `unexecuted` with their prerequisites named above.

## Commit Plan

Proposed implementation checkpoints; no commit is made by planning.

1. After Tasks 1-3: `feat(v4): own the diplomacy capability contract`
2. After Tasks 4-6: `feat(v4): define owner-scoped diplomacy beliefs and frames`
3. After Tasks 7-11: `feat(v4): collect and recognize diplomacy without authority`
4. After Tasks 12-15: `feat(v4): analyze inter-society relations and diplomacy metrics`
5. After Tasks 16-19: `feat(v4): publish diplomacy-snapshot-v1`
6. After Tasks 20-21: `feat(v4): serve read-only diplomacy surfaces`
7. After Tasks 22-26: `test(v4): enforce diplomacy invariants and certify`

## Blocking Conditions and Non-Goals

- Adding a new V4 flag, `runner-config-v57`, a new context, a runner root field,
  or a per-agent runner key to make this plan work is a blocking scope
  violation. Stop and re-plan.
- Claiming `organized_conflict`, `infrastructure_networks`, `supply_chains`,
  `markets_credit`, `science`, `epidemics`, `ecological_feedback`, `disasters`,
  `institutional_economy`, or `multi_hop_testimony_tracking` is forbidden.
- Creating a `DiplomacyAuthority`, `EnvoyRegistry`, `TreatyStore`,
  `TreatyAuthority`, `LegitimacyOracle`, `TruthEngine`, `Polity`, `Border`,
  `Citizenship`, `WarState`, `ArmyActor`, `RelationScore`, or binding agreement
  is forbidden.
- Computing, storing, publishing, or rendering a bilateral relationship score,
  valence, rank, trust value, composite index, or "overall relation" is
  forbidden.
- Letting `WorldEngine`, perception, admission, stop selectors, memory, prompts,
  observer semantics, or the Godot client read a diplomacy ledger is forbidden.
- Letting a diplomacy helper return, construct, submit, or resolve an
  `AgentCommand`, move a resource, or execute a physical action is forbidden.
- Treating envoy recognition, agreement acceptance, or scope as permission,
  prohibition, legitimacy, authenticity, truth, guilt, liability, or a binding
  finding is forbidden.
- Inferring contact, an envoy, a negotiation, a declaration, or acceptance from
  silence, an unobserved act, or another owner's ledger is forbidden.
- Treating a peer-supplied frame `provenance` or `mandate_ref` as trusted, or
  deriving current envoy standing only from the accreditation-time status, is
  forbidden.
- Counting one-way `Given` transfers as trade, or presenting a relation as a
  bilateral score, is forbidden.
- Publishing raw agent ids, free-text subjects, or frame bodies instead of
  hashed tokens and owner-safe anchors is forbidden.
- Reading a peer owner's relationship, reputation, commitment, rule, office,
  institution, organization, decision, dispute, evidence, or representation
  ledger to evaluate diplomacy is forbidden.
- Reconciling conflicting envoys or agreements into one authoritative
  representative or treaty is forbidden. Analysis may classify envoy alignment
  for researchers only.
- Minting, renaming, splitting, merging, or dissolving `org-` or `msoc-`
  identities from diplomacy analysis is forbidden.
- Adding a new event, command, observer semantic type, write pair, artifact kind,
  wire record genre, `/v2` route, `observer-protocol-v2` serving, or SQL
  migration is forbidden. The documented relation/termination rows are owner
  beliefs inside the existing snapshot/persistence seam, not new wire genres.
- Rewriting the V3 contact, migration, commitment, collective-project, mediation,
  office, institution, or V4 organization/formal-rule/dispute/evidence/
  representation contracts is forbidden; diplomacy is additive.
- Weakening an existing pin or assertion (catalog counts, Alembic `0017`, replay
  v22, codec v20, command count, observer semantic count, context count) is
  forbidden. The only intentional pin changes are 160 -> 164 metric families, the
  four-owned V4 flag set, the addition of six diplomacy routes alongside the
  existing route sets, and the new diplomacy snapshot/store schemas.
- Claiming prevalence, emergence probability, predictive power, accuracy,
  reliability of envoys in general, moral correctness, or a composite legitimacy
  score is forbidden.
- Editing `.ai-factory/ROADMAP.md` or closing M8 is out of scope;
  `$aif-roadmap` owns that.
- Changing the Godot client, observer protocol, observer capabilities, or
  `/version` is out of scope; the Research UI is the only client change.
- Enabling V4 flags in matrix lanes is out of scope; `experiments.matrix_schema`
  keeps its rejection gate.
- V4-10 does not add a command selector, prompt, or speech-generation bias.
  Diplomacy is a belief; a later plan that lets it bias behavior must be
  separately owned.
- Full qualification requires a disposable PostgreSQL/pgvector instance, Docker,
  a real browser driver, and the pinned Node/pnpm and Godot toolchains. A missing
  prerequisite leaves the lane unexecuted and blocks certification; it never
  becomes a skip-pass.
- Do not implement any other V4 context in this plan.

## Definition of Done

- All 26 indexed tasks have verified completion evidence; only this index holds
  task progress checkboxes.
- `diplomacy` is owned; no `v57`, new flag, context, root field, or per-agent
  runner key exists; `organized_conflict` remains unowned and fail-closed.
- The context registry validates at 14 contexts, 12 flags,
  `v4-context-map-v2`, and four owned flags.
- A general owner-scoped diplomacy ledger exists with five closed party kinds,
  closed contact/envoy/negotiation/instrument/term/termination/provenance/
  misrepresentation/conflict vocabularies, a retained `DiplomaticRelation` row
  with an ordered party set and owner self-party, a retained
  `DiplomaticTermination` row, bounded caps, and retained history.
- Every `relation_id`, `party_id`, `envoy_ref`, and `instrument_id` resolves
  inside the ledger; instruments carry their ordered party set and assertions
  cannot invent a party.
- Long-running relations accumulate contacts, envoys, negotiations, proposals,
  promises, agreements, disputes, and shared projects across ticks without a
  score, valence, rank, or composite.
- Envoy standing is derived from the owner's representation ledger and recomputed
  at detection/export/compose time; a self-claim stays claimed, and
  absent/contested/rejected/revoked/expired/superseded authority is retained.
- An agreement is `apparently_accepted` only with every party's own declaration:
  a principal declaration counts directly, an envoy declaration requires
  recognized standing, and no agreement binds anyone.
- The closed scope/duration matrix decides `scope_exceeded`; a `single_act` or
  `occasion` mandate never recognizes a long-running agreement and a named scope
  subject must match.
- Misrepresentation has exactly four closed kinds and no truth/lie/guilt field.
- Same-root declarations never count twice; one actor cannot satisfy two parties.
- A speaker cannot attribute a contact, envoy, or declaration to another party;
  mismatched frames are dropped with a notice.
- Termination, expiry, supersession, and conflicts are explicit and retained;
  two recognized agreements may coexist.
- The update materializes every derived row family through one ordered pipeline
  (append -> derive -> detect misrepresentation -> expire -> supersede -> detect
  conflicts -> enforce limits) with content-addressed dedupe.
- Detached analysis derives relation evidence from exactly six lanes (agent
  relationships, trade, conflict, agreements, narratives, institutional
  interaction); the trade lane counts `ExchangeCompleted` only and never one-way
  `Given` transfers. It keeps three layers separate with a hard leakage guard
  and classifies envoy alignment for researchers only.
- Diplomacy tokens interoperate with V4-09 analysis: agent identities hash in
  the same domain, while `orgc-` and region anchors stay owner-safe for
  `org-`/`msoc-` joins.
- The metric catalog is exactly 164 with four appended families; the first 160
  are unchanged, and real completed-run assembly emits all four documents.
- No test file or current-pin doc line still asserts 160; the stale-pin guard
  passes, while historical revision statements and the first-154 digest pin are
  preserved. The measured sweep covers 49 test files / 78 `== 160` occurrences
  and the current doc lines, and does not rewrite historical seam pins.
- `diplomacy-snapshot-v1` and `diplomacy-store-v1` are canonical, bounded,
  atomic, and immutable after publication; organization, formal-rule, dispute,
  evidence, and representation snapshots remain decodable and byte-verifiable.
- Snapshot rows and API responses contain only hashed owner/party/envoy/actor
  tokens and owner-safe `orgc-`/region anchors; no raw agent id, free-text
  subject, or frame body is published.
- Simulation snapshot rows use `DiplomacySnapshot*Row` names and the publication
  id mirrors the two-argument content-addressed precedent.
- Six GET-only `/v1` diplomacy routes require `SUBJECTIVE_DEBUG`, have an
  explicit `diplomacy_disabled` state, return 404 for an unknown published
  relation/instrument, and are consumed by a read-only Research UI view that
  derives no authority, score, or winner.
- Cursor reuse works on every paged diplomacy route; a changed
  run/publication/digest/purpose/filter fails with 400 and expiry with 410.
- `WorldEngine` never reads a diplomacy ledger; a rejected or contested envoy
  does not block a physically possible command, and a physically impossible
  command is still rejected.
- The boundary suite proves owner-only authority, the absence of score/legitimacy/
  treaty/polity/envoy registries, no command construction, no peer-ledger reads,
  no world-ledger reads, and no `org-`/`msoc-` mutation; no new
  commands/events/migrations are added; observer and migration pins are unchanged.
- The focused in-process diplomacy E2E runs without PostgreSQL in the
  focused/unit lane and is never reported as an integration-only prerequisite.
- The full V1-V4 regression lanes and static gates execute and pass; any
  unexecuted required lane is reported with its blocker and is not certified.
- Documentation states what diplomacy controls (a belief), what it never controls
  (objective action, permission, truth, or a binding agreement), how relation
  records and self-parties, contact, envoys, negotiations, instruments,
  misrepresentation, termination, and frames work, how representation composes,
  and every count matches the code. The docs sweep updates every current
  four-owned/eight-unowned statement and leaves historical seam pins intact.
- `docs/diplomacy.md` is the canonical contract; `docs/analysis-metrics.md`
  documents the four families, `docs/research-ui.md` documents the panel, and
  README plus `docs/organizations.md` and `docs/delegation-representation.md`
  link the new contract.
