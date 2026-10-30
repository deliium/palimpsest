<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-03 General Organization Model

Mode: ultra
Branch: main (remain on current branch; `git.create_branches: false`)
Created: 2026-10-30
Plan identifier: `v4-03-organizations`
Status: ready for implementation; 22 tasks across 8 phases.

## Original Request

v4-03 general organization model

Naming requirement:

Use canonical `v4-03-organizations`.

Implement a generic emergent Organization concept built from already existing V3 institutional primitives.

Support:

- perceived membership

- roles

- shared goals

- shared resources

- procedures

- records

- internal commitments

- identity concepts

- historical lineage

Do NOT create hard-coded classes such as:

Government
Church
Corporation
Army
University
Guild

Organizations must be general enough that different structures emerge from the same low-level mechanics.

Membership may be:

- explicit

- disputed

- unknown

- overlapping

- temporary

An Organization must not receive an independent omniscient cognition engine.

All organization activity ultimately occurs through agents, records, roles and recognized procedures.

## Settings

- Testing: yes; full strategy. Unit, architecture, integration, Compose/browser,
  Godot regression, Research UI, benchmark regression, and static gates, with
  coverage enabled for Python lanes.
- Logging: verbose, metadata-only. Bounded DEBUG flow/counts, INFO milestones,
  WARN incomplete evidence, ERROR safe codes. `PALIMPSEST_LOG_LEVEL` controls
  operational verbosity. No person sets, private content, payload surrogates,
  prompts, credentials, tokens, DSNs, memories, or embeddings.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 21.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints are suggestions, not authorization to
  commit during planning.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-03-organizations`; the ultra bundle directory is
  `.ai-factory/plans/v4-03-organizations/`, phase files use
  `phase-NN-<slug>.md`, and `index.md` is the canonical entrypoint.
- Research source: `.ai-factory/RESEARCH.md` and `.ai-factory/research/` do not
  exist; no external research conclusions are invented.
- Execution: planning only in this invocation.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"
Rationale: V4-03 owns the first flagged V4 context, `organizations`, on the
existing V4-01 `runner-config-v56` seam. This plan does not edit or close the
roadmap; `$aif-roadmap` must register V4-03 in M8.

## Requirements Reconciliation

Authority: the Original Request defines scope; `.ai-factory/ARCHITECTURE.md`
("Key Principles", "Capability ownership", "Important V3 seams", "Versioned
Extension Contract", V4-01/V4-02 seams) and `.ai-factory/RULES.md` constrain
every edit; `.ai-factory/DESCRIPTION.md` and `.ai-factory/ROADMAP.md` describe
current state; completed V4-01/V4-02 code, pins, and the
`tests/architecture/test_v4_*` suites govern compatibility. V4-03 owns the
owner-scoped `organizations` context; it may not create an objective organization
actor, roster, treasury, registry, or independent cognition engine.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-03 owns exactly one V4 flag, `organizations`, on the existing `runner-config-v56`; the other eleven stay unowned and fail closed | Original Request "generic emergent Organization concept"; `.ai-factory/ARCHITECTURE.md` "Capability ownership"; `src/simulation/runner_models.py` 305-322 | Task 1 ownership split; Task 19/22 pins |
| No `runner-config-v57`, new root field, or per-agent runner mode is added; the flag is the declared seam and enables one locked deterministic policy | V4-01 contract: v56 is the active v55 keyset plus one `v4_capability_flags` sibling; `src/simulation/v4_architecture.py` 103-117 | Task 1 `v57` absence; Task 6 flag-to-cognition wiring; Task 22 grep |
| The context registry stays at 14 contexts, 12 flags, and `v4-context-map-v2`; the analysis-only set and four reservations are unchanged | V4-02 index Definition of Done; `tests/architecture/test_v4_context_registry.py` 99-200 | Task 1/19 registry assertions |
| `organizations` remains owner-scoped with owners `agents.cognition`, `social`, `simulation`, prerequisites `()`, and `uses_existing_events=True`; it claims no write pair | `src/simulation/v4_architecture.py` 104-117; `src/simulation/versioning.py` 77-90 | Task 1 no-reservation assertion; Task 19 `V4_EVENT_REUSING_CONTEXTS` |
| The nine requested aspects are owner-scoped belief records referencing existing primitives, not new objective state | Original Request list; `agents/cognition/institution_concepts.py`, `offices.py`, `institutional_memory.py`, `collective_decisions.py`, `structured_commitments.py`, `group_formation.py`; `world/artifacts.py`, `world/repositories.py`, `world/collective_projects.py` | Tasks 3-4 record/ledger tests; Task 19 no-world-authority scan |
| Membership supports `explicit`, `perceived`, `disputed`, `unknown`, `former`, `ongoing`/`temporary`; overlap is legal and no exclusive partition exists | Original Request membership list; `group_formation.py` overlapping beliefs; `society_emergence.py` exclusive contract is not reused | Task 5/8 overlap, dispute, expiry tests |
| Explicit and disputed membership have a bounded self-authored speech path using existing `Talk`/`Tell`; no new command, event, observer semantic type, or free-text payload | `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts"; V3 collective-decision/institutional-memory relation precedent | Task 4 frame tests; Task 19 command/event pins |
| Roles reference the owner's `OfficeConcept`; duties and authority remain beliefs and never become permissions | `.ai-factory/ARCHITECTURE.md` "Important V3 seams" V3-30; `offices.py` 777-1129 | Task 3/4 role-reference tests; Task 19 no-permission scan |
| Shared goals reference `CollectiveProposal`/collective projects; shared resources reference observed repositories/artifacts/stored resources; records reference artifacts/repositories; commitments reference owner interpretation ids | `collective_decisions.py` 512-643; `world/collective_projects.py`; `world/repositories.py` 148-278; `world/artifacts.py` 314-528; `agents/cognition/structured_commitments.py` 88-235 | Task 3 anchor tests; Task 5 formation tests; Task 12 snapshot fields |
| No organization-owned resource pool, treasury, roster, or registry exists; all resources stay objective or referenced | V4-01 `organizations` non-goals `src/simulation/v4_architecture.py` 113-116; `docs/v4-architecture.md` organizations section | Task 19 treasury/roster/registry scan; Task 21 docs |
| No hard-coded Government/Church/Corporation/Army/University/Guild or equivalent class exists; structure emerges from low-level mechanics | Original Request "Do NOT create hard-coded classes" | Task 2 forbidden-token contract; Task 19 magic-actor scan; Task 21 docs |
| The organization ledger reads only the owner's own observation and prepared ledgers; it never reads `WorldState`, peer ledgers, event stores, or commands | Original Request "must not receive an independent omniscient cognition engine"; `.ai-factory/ARCHITECTURE.md` "Objective authority and runtime" | Task 5/6 isolation tests; Task 19 AST checks |
| Owner-local `orgc-`, analytical `org-`, and publication `org-edge-` identities are content-addressed from creation evidence and never derived from current membership alone or a mutable counter | Original Request "historical lineage"; `.ai-factory/ARCHITECTURE.md` "Key Principles" 2; V4-02 `derive_macro_society_id` precedent | Task 2/4/9 identity tests; Task 19 determinism |
| Analytical lineage records `continued`, `transformed`, `split`, `merge`, `dissolved`, `emerged`; edges are forward-only, acyclic, and deterministic; split/merge mint new ids | Original Request "historical lineage"; V4-02 lineage precedent | Task 10 fixtures; Task 19 Hypothesis acyclicity |
| Objective structure counts, owner-scoped subjective claims, and analytical candidates are three distinct types with hard leakage checks | Original Request distinction of perceived vs researcher views; `.ai-factory/ARCHITECTURE.md` "Key Principles" 1 | Task 10 layer tests; Task 19 leakage property |
| The metric catalog grows from 140 to 144 with four appended families; every existing family keeps id, order, version, and value keys | `src/analysis/specifications.py` `METRIC_FAMILY_COUNT` 53; `_BUILDERS` 6202-6343; `validate_metric_catalog` 6364-6397 | Task 11 registration and exact pin updates; Task 19/22 144 |
| `organization-snapshot-v1` is new, canonical, bounded, immutable, and independent of analysis types | `.ai-factory/ARCHITECTURE.md` "Use accepted-set and exact-key-set schema evolution"; `simulation/macro_society_*` precedent | Task 12 codec/caps; Task 19 schema independence |
| Access is four GET-only `/v1` routes requiring `SUBJECTIVE_DEBUG` with explicit `organization_disabled` | `docs/research-api.md`; `src/api/routes/macro_society.py` precedent | Task 16 route tests; Task 19 GET-only scan |
| Publication is opt-in, post-completion, and isolated from scientific status | V4-02/V3-39 precedent; `.ai-factory/ARCHITECTURE.md` "Read-only presentation" | Task 14/17 receipts; Task 19 failure isolation |
| Observer protocol, observer capabilities, Godot, and `/version` are unchanged; `organization_rows` stays reserved | V4-01/V4-02 pins; `src/observer/capabilities.py` 17-46 | Task 19 equality assertions; Task 22 pin audit |
| No SQL migration: the artifact is a filesystem publication; Alembic stays `0017` | `.ai-factory/ARCHITECTURE.md` requirement 5 | Task 15/19/22 Alembic pin; `git status alembic/` |
| Required lanes must execute; a missing prerequisite is reported as unexecuted, never as a skip-pass | Plan Settings "Testing: yes; full strategy"; `docs/development.md`; `tests/compose/acceptance.py` | Task 20 three-state receipt; Task 22 certification audit |
| The roadmap is owned by `$aif-roadmap` and is not edited here | `.ai-factory/ARCHITECTURE.md` requirement 7 | Task 21/22 `git status` |

### Supported combinations and availability transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| Default runner config, all V4 flags off | V3/V4-02-equivalent behavior | No organization code path; no ledger, policy, metric, or publication | Task 6/19 flags-off tests |
| `organizations` enabled on v4 or v55 | Unchanged config | `v4_capability_requires_v56` before construction | Task 1 test |
| `organizations` enabled on v56, no V3 evidence modes | Valid run | Empty typed ledger per owner; metrics `ABSENT`; no fabricated organization | Task 6/8/11 tests |
| Institution concepts only | Procedure evidence | Candidate with procedures but no roles; `PARTIAL`/candidate status | Task 5/8/11 tests |
| Offices only | Role evidence | Candidate with roles but no procedures; `PARTIAL`/candidate status | Task 5/8/11 tests |
| Group formation only | Perceived membership | Candidate with membership and identity but no structural channels; candidate status | Task 5/8 tests |
| Self-authored claim plus contrary observation | Dispute | Member `disputed`; candidate `disputed`; no forced membership | Task 4/5/8 tests |
| One person in two concepts | Overlap | Both candidates retained; person in `overlap_member_ids` | Task 8 test |
| Temporary claim reaches `expires_tick` | Expiry | Member `former`; concept `dissolved` when no other evidence | Task 5/8 tests |
| One concept splits into two | New children | Two new `org-` ids; `split` lineage edge; owner-local predecessors retained | Task 5/10 test |
| Two concepts merge | New result | One new `org-` id; `merge` lineage edge; predecessors dissolved | Task 5/10 test |
| Missing objective anchor | Unresolved reference | Anchor row `resolved=False`; `PARTIAL`; no zero inference | Task 7/8/11 tests |
| Candidate exceeds 512 members | Deterministic truncation | Member list truncated with `provenance_code="member_list_truncated"` | Task 14 test |
| Snapshot exceeds 4 MiB or 2048 candidates | No publication | `organization_size_limit` | Task 12/14 test |
| Duplicate publication id with different bytes | Existing publication untouched | `organization_publication_exists` | Task 15 test |
| `PALIMPSEST_ORGANIZATION_ROOT` unset | API state unset | 503 `organization_disabled`; CLI receipt `disabled` | Task 16/17 tests |
| Cursor reused with a changed filter, run, or publication | No page served | 400 `organization_cursor_invalid`; expired 410 | Task 16 test |
| Run incomplete or publication failed | Scientific result unchanged | Receipt `unavailable`/`failed` only | Task 17 test |
| Required Compose/browser/Godot lane with a missing prerequisite | No green certification | Recorded `unexecuted` with prerequisite | Task 20/22 |

## Architecture and Decisions

1. **One owned flag, one seam.** `organizations` is added to
   `_V4_OWNED_CAPABILITY_FLAGS` and the public compatibility set. Enabling it
   requires the already-accepted `runner-config-v56`; no `v57` is introduced.
2. **Owner-scoped, not objective.** An organization is a belief one agent holds
   about a recurring collective structure. It is not a `WorldEngine` entity and
   has no roster, treasury, permissions, or commands.
3. **Nine aspects, references only.** Perceived members, roles, goals,
   resources, procedures, records, commitments, identity, and history are belief
   records. Roles reference owner-local offices; goals reference collective
   proposals/projects; resources and records reference objective anchors;
   commitments reference owner interpretations.
4. **No independent cognition engine.** The ledger reads only the owner's
   observation and prepared owner ledgers. It never reads peer ledgers, world
   state, event stores, or another agent's perspective. All activity remains
   ordinary agent commands, speech, records, roles, and recognized procedures.
5. **Membership is not a partition.** `explicit`, `perceived`, `disputed`,
   `unknown`, and `former` statuses coexist; a person may belong to several
   concepts; temporary membership expires explicitly.
6. **Identity is minted once.** Owner-local `orgc-` ids derive from owner,
   creation tick, founding members, and first structural anchors. Continuation
   inherits; split children and merge results mint new ids.
7. **Lineage is forward-only.** `continued`, `transformed`, `split`, `merge`,
   `dissolved`, `emerged`; edges are monotone in ticks and validated acyclic.
8. **Three layers, three types.** Objective rows are counts only; subjective
   rows carry `orgc-` ids and owner claims; analytical candidates carry `org-`
   ids. Leakage is a hard failure.
9. **Deterministic by construction.** Sorted ordering, canonical JSON digests,
   quantized floats, no `hash()`, no UUID, no wall-clock in domain values.
10. **The artifact is independent.** `organization-snapshot-v1` lives in
    `simulation`; analysis never imports persistence, and persistence never
    imports analysis.
11. **Publication is opt-in and non-interfering.** Completed-run publication
    through `research_runner`; a storage failure changes only the receipt, never
    scientific status.
12. **Read-only presentation.** Four GET routes under `/v1` require
    `SUBJECTIVE_DEBUG`; the Research UI performs no client-side derivation.
13. **No capacity or prevalence claim.** Counts describe detached candidates
    under stated coverage; no probability, capacity, throughput, or prediction.
14. **Compatibility is additive.** Runner v4/v55/v56, result v2/v3, events 22,
    codec v20, commands 43, observer semantic types 73, Alembic `0017`, `/v1`,
    `observer-protocol-v1`, and the four reserved write pairs are unchanged.
15. **The metric catalog grows to 144.** Four appended families: formation,
    membership, structure, lineage. Existing families keep id, order, version,
    and value keys.
16. **Matrix V4 lanes remain out of scope.** `experiments.matrix_schema.finalize`
    still rejects enabled V4 flags; V4-03 is exercised through explicit v56
    single-run configs.
17. **Public contracts land in facades.** New analysis, simulation, experiments,
    and persistence symbols are re-exported in the same change, matching the
    V4-02 macro-society convention.
18. **Checkpoint continuity is tested through the runner.** The real
    `export_runtime_checkpoint()` → `apply_runtime_checkpoint()` path is the
    evidence, not a hand-built ledger copy. The loop fork-state version stays
    `cognitive-loop-fork-state-v1` because the new field is optional and
    process-local.
19. **The artifact publishes objective aggregates and analytical candidates.**
    Owner-scoped claim detail remains in the detached analysis layer; member
    records carry aggregated status and `owner_support_count`, never owner ids
    or `orgc-` ids.

### Context declaration

| Context | Flag | Authority | Owning packages | Prerequisites | Existing mechanism | Event strategy |
| --- | --- | --- | --- | --- | --- | --- |
| `organizations` | `organizations` (owned) | owner-scoped | `agents.cognition`, `social`, `simulation` | none | collective projects, public goods, mentorship, institution concepts, offices, institutional memory, collective decisions, structured commitments, group formation | reuse |

### Unchanged compatibility pins

Default runner/result `v4`/`v2`; latest feature runner `v55`; accepted runner adds
`v56` only; events `EVENT_SCHEMA_REPLAY_V22` (22); codec `v20`; commands 43;
observer semantic types 73; metric families 144 (V4-03 change); Alembic `0017`;
`/v1`; `observer-protocol-v1`; observer layout `observer-layout-v1`; observer
capabilities 4 advertised / 6 reserved; four reserved write pairs (events 23-26 /
codecs `v21`-`v24`); `prepare_parallel=False`.
`institutional_economy` and `multi_hop_testimony_tracking` remain unowned and
fail closed. `/version` is unchanged; `organization_rows` remains reserved.

## Phase Index

1. [Phase 1: Ownership and Closed Contract](phase-01-ownership-and-contract.md) — Tasks 1-2
2. [Phase 2: Owner-Scoped Organization Concepts](phase-02-owner-scoped-concepts.md) — Tasks 3-6
3. [Phase 3: Detached Analysis, Identity, Lineage, and Metrics](phase-03-detached-analysis.md) — Tasks 7-11
4. [Phase 4: Organization Snapshot Contract](phase-04-snapshot-contract.md) — Tasks 12-13
5. [Phase 5: Composition and Durable Publication](phase-05-publication.md) — Tasks 14-15
6. [Phase 6: Read-Only API, CLI, and Research UI](phase-06-surfaces.md) — Tasks 16-18
7. [Phase 7: Invariants and Regression](phase-07-invariants-and-regression.md) — Tasks 19-20
8. [Phase 8: Documentation and Final Verification](phase-08-docs-and-verification.md) — Tasks 21-22

## Cross-Phase Dependencies

- Task 2 depends on Task 1: the contract's flag ownership and non-goals must match
  the owned registry entry.
- Task 3 depends on Task 2: belief records use the frozen enums, policy, and ID
  grammar.
- Task 4 depends on Task 3: the bounded speech claim grammar uses the frozen
  identity/status vocabulary.
- Task 5 depends on Tasks 3-4: formation consumes the claim parser and the frozen
  records.
- Task 6 depends on Tasks 4-5: the ledger must exist and parse claims before it is
  carried through cognition and checkpoints.
- Task 7 depends on Task 6: the harvest reads exported owner ledgers.
- Task 8 depends on Task 7: detection consumes normalized windows.
- Task 9 depends on Task 8: identity assignment matches detected candidates.
- Task 10 depends on Tasks 8-9: layers and lineage consume candidates and
  assignments.
- Task 11 depends on Tasks 8-10: all four families read the analysis object.
- Task 12 depends on Tasks 10-11: the snapshot mirrors analysis records and metric
  provenance.
- Task 13 depends on Task 12: paging selects typed records and the ports carry
  the codec.
- Task 14 depends on Tasks 11 and 13: the bridge needs analysis and the ports.
- Task 15 depends on Task 13: the store implements the ports.
- Task 16 depends on Task 15: the API reads the committed store.
- Task 17 depends on Tasks 14-15: the CLI builds a harvest and publishes it.
- Task 18 depends on Task 16: the panel consumes the four routes.
- Task 19 depends on Tasks 2-18: the suite asserts every authority claim.
- Task 20 depends on Task 19: regression runs only after the invariant gate is
  green.
- Task 21 depends on Tasks 2-20: documentation describes verified surfaces.
- Task 22 depends on Tasks 20-21: final certification needs receipts and docs.

## Tasks

### Phase 1: Ownership and Closed Contract
- [x] Task 1: Own the organizations context on runner-config-v56 ([details](phase-01-ownership-and-contract.md#task-1-own-the-organizations-context-on-runner-config-v56))
- [x] Task 2: Freeze the closed organization contract ([details](phase-01-ownership-and-contract.md#task-2-freeze-the-closed-organization-contract)) (depends on 1)

### Phase 2: Owner-Scoped Organization Concepts
- [x] Task 3: Define organization belief records and ledger invariants ([details](phase-02-owner-scoped-concepts.md#task-3-define-organization-belief-records-and-ledger-invariants)) (depends on 2)
- [x] Task 4: Add bounded organization claims in existing speech ([details](phase-02-owner-scoped-concepts.md#task-4-add-bounded-organization-claims-in-existing-speech)) (depends on 3)
- [x] Task 5: Implement deterministic formation, recognition, revisions, and owner-local lineage ([details](phase-02-owner-scoped-concepts.md#task-5-implement-deterministic-formation-recognition-revisions-and-owner-local-lineage)) (depends on 3, 4)
- [x] Task 6: Integrate the ledger through cognition, checkpoints, and the runner ([details](phase-02-owner-scoped-concepts.md#task-6-integrate-the-ledger-through-cognition-checkpoints-and-the-runner)) (depends on 4, 5)

### Phase 3: Detached Analysis, Identity, Lineage, and Metrics
- [x] Task 7: Harvest owner ledgers into detached organization rows ([details](phase-03-detached-analysis.md#task-7-harvest-owner-ledgers-into-detached-organization-rows)) (depends on 6)
- [x] Task 8: Detect overlapping cross-owner organization candidates ([details](phase-03-detached-analysis.md#task-8-detect-overlapping-cross-owner-organization-candidates)) (depends on 7)
- [x] Task 9: Assign stable analytical organization identities ([details](phase-03-detached-analysis.md#task-9-assign-stable-analytical-organization-identities)) (depends on 8)
- [x] Task 10: Project three layers and derive forward-only lineage ([details](phase-03-detached-analysis.md#task-10-project-three-layers-and-derive-forward-only-lineage)) (depends on 8, 9)
- [x] Task 11: Emit four metric families and raise the catalog to 144 ([details](phase-03-detached-analysis.md#task-11-emit-four-metric-families-and-raise-the-catalog-to-144)) (depends on 8, 9, 10)

### Phase 4: Organization Snapshot Contract
- [x] Task 12: Define snapshot models and the canonical codec ([details](phase-04-snapshot-contract.md#task-12-define-snapshot-models-and-the-canonical-codec)) (depends on 10, 11)
- [x] Task 13: Add paging, read/publication ports, and cursor DTO ([details](phase-04-snapshot-contract.md#task-13-add-paging-readpublication-ports-and-cursor-dto)) (depends on 12)

### Phase 5: Composition and Durable Publication
- [x] Task 14: Compose completed-run organization snapshots ([details](phase-05-publication.md#task-14-compose-completed-run-organization-snapshots)) (depends on 11, 13)
- [x] Task 15: Implement the atomic quota-bounded filesystem store ([details](phase-05-publication.md#task-15-implement-the-atomic-quota-bounded-filesystem-store)) (depends on 13)

### Phase 6: Read-Only API, CLI, and Research UI
- [x] Task 16: Add settings and GET-only API routes ([details](phase-06-surfaces.md#task-16-add-settings-and-get-only-api-routes)) (depends on 15)
- [x] Task 17: Compose the producer in research_runner ([details](phase-06-surfaces.md#task-17-compose-the-producer-in-research_runner)) (depends on 14, 15)
- [x] Task 18: Add the read-only Research UI panel ([details](phase-06-surfaces.md#task-18-add-the-read-only-research-ui-panel)) (depends on 16)

### Phase 7: Invariants and Regression
- [x] Task 19: Add the organization boundary and determinism suite ([details](phase-07-invariants-and-regression.md#task-19-add-the-organization-boundary-and-determinism-suite)) (depends on 2-18)
- [x] Task 20: Execute the full V1-V4 regression and qualification lanes ([details](phase-07-invariants-and-regression.md#task-20-execute-the-full-v1-v4-regression-and-qualification-lanes)) (depends on 19)

### Phase 8: Documentation and Final Verification
- [x] Task 21: Execute the documentation checkpoint ([details](phase-08-docs-and-verification.md#task-21-execute-the-documentation-checkpoint)) (depends on 2-20)
- [x] Task 22: Perform final V4-03 verification ([details](phase-08-docs-and-verification.md#task-22-perform-final-v4-03-verification)) (depends on 20, 21)

## Commit Plan

Proposed implementation checkpoints; no commit is made by planning.

1. After Tasks 1-2: `feat(v4): own the organizations context and freeze its contract`
2. After Tasks 3-6: `feat(v4): form owner-scoped organization concepts`
3. After Tasks 7-11: `feat(v4): derive analytical organization candidates and metrics`
4. After Tasks 12-15: `feat(v4): publish bounded organization snapshots`
5. After Tasks 16-18: `feat(v4): serve read-only organization views`
6. After Tasks 19-22: `test(v4): enforce organization invariants and regression`

## Blocking Conditions and Non-Goals

- Adding `runner-config-v57`, a new runner root field, or a per-agent runner mode
  to make this plan work is a blocking scope violation. Stop and re-plan.
- Adding a capability flag other than `organizations`, a new event, command,
  observer semantic type, write pair, `/v2` route, `observer-protocol-v2` serving,
  or SQL migration is forbidden.
- Creating an objective Organization, Government, Church, Corporation, Army,
  University, Guild, State, Nation, Polity, Empire, Tribe, Ministry, Department,
  Treasury, Bank, Court, Police, Party, or global organization registry is
  forbidden.
- Giving `WorldEngine`, perception, cognition, memory, prompts, admission, or stop
  selectors a read of an organization candidate or another owner's ledger is
  forbidden.
- Creating an organization-owned resource pool, treasury balance, membership
  roster, objective role assignment, or organization-owned record store is
  forbidden.
- Requiring exclusive membership, forcing self-identification, or treating a
  candidate as a census is forbidden.
- Claiming capacity, prevalence, emergence probability, predictive power, or a
  composite civilization score is forbidden.
- Editing `.ai-factory/ROADMAP.md` or closing M8 is out of scope;
  `$aif-roadmap` owns that.
- Changing the Godot client, observer protocol, observer capabilities, or
  `/version` is out of scope; the Research UI is the only client change.
- Enabling V4 flags in matrix lanes is out of scope; `experiments.matrix_schema`
  keeps its rejection gate.
- Weakening an existing pin or assertion (catalog counts, Alembic `0017`, replay
  v22, codec v20, command count, observer semantic count, context count) is
  forbidden. The only intentional pin change is 140 -> 144 metric families.
- Full qualification requires a disposable PostgreSQL/pgvector instance, Docker,
  a real browser driver, and the pinned Node/pnpm and Godot toolchains. A missing
  prerequisite leaves the lane unexecuted and blocks certification; it never
  becomes a skip-pass.
- Do not implement any other V4 context (`formal_rules`, `legal_disputes`,
  `diplomacy`, `organized_conflict`, `infrastructure_networks`, `supply_chains`,
  `markets_credit`, `science`, `epidemics`, `ecological_feedback`, `disasters`,
  `societal_resilience`, `macro_society_identity`) in this plan.

## Definition of Done

- All 22 indexed tasks have verified completion evidence; only this index holds
  task progress checkboxes.
- `organizations` is the one owned V4 flag on the existing `runner-config-v56`;
  the other eleven still fail closed; no `v57` exists.
- The context registry validates at 14 contexts, 12 flags, and
  `v4-context-map-v2`; the analysis-only set and four reservations are unchanged.
- Owner-scoped beliefs cover perceived membership, roles, shared goals,
  referenced resources, procedures, records, internal commitments, identity
  concepts, and bounded history.
- Membership supports explicit, perceived, disputed, unknown, former, ongoing,
  and temporary states; overlap is legal; no partition exists.
- No hard-coded Government/Church/Corporation/Army/University/Guild or equivalent
  class exists; structure emerges from the same low-level mechanics.
- The organization ledger reads only owner observation and prepared owner
  ledgers; no peer ledger, world state, command, or independent cognition engine
  exists.
- `orgc-`, `org-`, and `org-edge-` identities are content-addressed from creation
  evidence; split children and merge results mint new ids.
- Analytical lineage records `continued`, `transformed`, `split`, `merge`,
  `dissolved`, and `emerged` edges that are forward-only, acyclic, and
  deterministic.
- Objective structure counts, owner-scoped subjective claims, and analytical
  candidates are three distinct types with passing leakage tests.
- The metric catalog is exactly 144 with four appended families and no change to
  existing families.
- `organization-snapshot-v1` is canonical, bounded, immutable after publication,
  and served through opt-in completed-run publication.
- Four GET-only `/v1` routes require `SUBJECTIVE_DEBUG`, have an explicit
  `organization_disabled` state, and are consumed by a read-only Research UI
  panel.
- The boundary suite proves owner-scoped authority, absence of magic actors and
  treasuries, no world or peer-state imports, no new commands/events/migrations,
  and unchanged observer/migration pins.
- The full V1-V4 regression lanes and static gates execute and pass; any
  unexecuted required lane is reported with its blocker and is not certified.
- Documentation states what an organization is, what it is not, how the nine
  aspects are referenced, how membership and identity behave, and how lineage is
  formed, with every count matching the code.
