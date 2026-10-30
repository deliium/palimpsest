<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-02 Macro-Society Analytical Identity

Mode: ultra
Branch: main (remain on current branch; `git.create_branches: false`)
Created: 2026-10-30
Plan identifier: `v4-02-macro-society-identity`
Status: planning complete; 20 tasks across 9 phases. No task is implemented by
this planning invocation.

## Original Request

v4-02 macro society analytical identity

Naming requirement:

Use canonical `v4-02-macro-society-identity`.

Implement research-level detection and representation of large society-like clusters.

Do NOT create objective Country, Nation or Civilization ownership over agents.

Derive candidate macro-societies from evidence such as:

- interaction networks

- migration

- shared institutions

- shared cultural traits

- communication

- economic exchange

- territorial patterns

- self-identification

- collective decisions

Distinguish:

objective population structure

agent subjective collective identity

researcher analytical macro-society candidate

Allow:

- overlapping identities

- disputed membership

- fragmented societies

- merging societies

- societies without explicit self-identification

Provide stable analytical IDs without turning them into WorldEngine authority.

Add lineage tracking so analytical societies can split/merge across historical time.

## Settings

- Testing: yes; full strategy. Unit, architecture, integration, Compose/browser,
  Godot regression, Research UI, benchmark regression, and static gates, with
  coverage enabled for Python lanes.
- Logging: verbose, metadata-only. Bounded DEBUG flow/counts, INFO milestones,
  WARN incomplete evidence, ERROR safe codes. `PALIMPSEST_LOG_LEVEL` controls
  operational verbosity. No person sets, private content, payload surrogates,
  prompts, credentials, tokens, DSNs, memories, or embeddings.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 19.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints are suggestions, not authorization to
  commit during planning.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-02-macro-society-identity`; the ultra bundle
  directory is `.ai-factory/plans/v4-02-macro-society-identity/`, phase files use
  `phase-NN-<slug>.md`, and `index.md` is the canonical entrypoint.
- Research source: `.ai-factory/RESEARCH.md` and `.ai-factory/research/` do not
  exist; no external research conclusions are invented.
- Execution: planning only in this invocation.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"
Rationale: V4-02 implements the first analysis-only V4 context,
`macro_society_identity`, under the M8 scaffolding landed by V4-01. This plan does
not edit or close the roadmap; `$aif-roadmap` must register V4-02 in M8.

## Requirements Reconciliation

Authority: the Original Request defines scope; `.ai-factory/ARCHITECTURE.md`
("Key Principles", "Versioned Extension Contract", V4-01 seam) and
`.ai-factory/RULES.md` constrain every edit; `.ai-factory/DESCRIPTION.md` and
`.ai-factory/ROADMAP.md` describe current state; completed V4-01 code, pins, and
the `tests/architecture/test_v4_*` suites govern compatibility. V4-02 is
analysis-only: it may detect, name, and record analytical candidates but may not
create objective peers, actors, or world authority.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-02 owns no capability flag and adds no runner schema; all V4 flags stay unowned and fail closed | Original Request "Do NOT create objective ... ownership"; `.ai-factory/ARCHITECTURE.md` "Capability ownership" | Task 17 asserts `V4CapabilityFlags().any_enabled() is False` and no macro module references a flag; Task 20 greps for `v4_capability_flags.` |
| The context registry grows from 13 to 14 contexts and `v4-context-map-v1` becomes `v4-context-map-v2` | V4-01 index Definition of Done; `tests/architecture/test_v4_context_registry.py` (99-116) | Task 1 updates the map version, count, analysis-only set, and doc headings; the registry test must pass at 14 |
| `macro_society_identity` is detached analysis that owns only `analysis` and reserves no write pair | `src/simulation/v4_architecture.py` `validate_v4_contexts` (358-367); `src/simulation/versioning.py` (134) | Task 1 registry entry plus the four-reservation assertion; Task 17 boundary suite |
| Candidates are derived from the nine requested evidence lanes using existing detached sources only — no new event, command, ledger, or route version | Original Request evidence list; `src/analysis/sources.py`, `society_emergence.py`, `collective_decisions.py`, `institutional_decay.py`, `cultural_trait_dynamics.py`, `structured_commitments.py`, `spatial_control_metrics.py`, `regional_population.py` | Task 3 adapters; Task 17 no-event/no-migration pin |
| Overlapping membership is legal and required; the existing exclusive `society_emergence@1` contract is preserved unchanged | Original Request "overlapping identities"; `SocietyEmissionResult.__post_init__` (249-256) rejects duplicates | Task 4 overlap tests; existing `test_society_emergence*` must stay green |
| Stable `msoc-` identity derives from creation evidence (creation tick, founding members, lane signature), never from current membership alone | Original Request "stable analytical IDs"; `derive_community_id` precedent (`society_emergence.py` 66-72) | Task 2 permutation and `PYTHONHASHSEED` tests; Task 6 churn tests |
| Split/merge lineage is deterministic, forward-only, and acyclic, with new ids for split children and merge results | Original Request "split/merge across historical time"; `group_formation_metrics._JACCARD` (53); `institution_lineage` kinds (46-50) and `_validate_acyclic` | Task 7 fixture and validation tests; Task 17 Hypothesis acyclicity property |
| Objective population structure, subjective identity claims, and analytical candidates are three distinct types with leakage checks | Original Request "Distinguish"; `.ai-factory/ARCHITECTURE.md` "Key Principles" 1 | Task 5 leakage tests; Task 12 end-to-end layer assertions |
| The metric catalog grows from 136 to 140 with four appended families; every existing family keeps id, order, version, and value keys | `src/analysis/specifications.py` `METRIC_FAMILY_COUNT` (53), `_BUILDERS` (6003-6140), `validate_metric_catalog` (6161) | Task 9 registration plus exact pin updates; Task 18 greps for stale 136 |
| Snapshot schema `macro-society-snapshot-v1` is new, bounded, canonical, and independent of analysis types | `.ai-factory/ARCHITECTURE.md` "Use accepted-set and exact-key-set schema evolution" | Task 10 codec strictness and size-cap tests |
| Access is `/v1` GET-only under the existing API version, requires `SUBJECTIVE_DEBUG`, and has an explicit disabled state | `docs/research-api.md` versioning policy; `src/api/routes/lineage.py` precedent | Task 14 route tests; Task 17 GET-only AST scan |
| Observer protocol, observer capabilities, Godot, and the `/version` payload are unchanged | V4-01 index "Unchanged compatibility pins"; `src/observer/capabilities.py` | Task 17 equality assertions; Task 20 pin audit |
| No SQL migration: the artifact is a filesystem publication; Alembic stays `0017` | `.ai-factory/ARCHITECTURE.md` requirement 5 ("Add SQL columns/migrations only for a proven persistence or indexed-inspection need") | Task 18/20 Alembic pin and `git status alembic/` |
| Required lanes must execute; a missing prerequisite is reported as unexecuted, never as a skip-pass | `tests/compose/acceptance.py`; Settings "Testing: yes; full strategy" | Task 18 three-state receipt; Task 20 certification audit |
| The roadmap is owned by `$aif-roadmap` and is not edited here | `.ai-factory/ARCHITECTURE.md` requirement 7 | Task 19 states the required update instead of performing it |

### Supported combinations and availability transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| Default runner config, all V4 flags off | V3-equivalent behavior | No macro-society code path is reachable from the runner | Task 17 flag-absence test |
| Any V4 flag enabled | V4-01 fail-closed gate | Unchanged `capability_unimplemented` at `SimulationRunner.from_config` | Task 17/20 |
| Harvest with zero windows | No publication | `macro_society_empty_window` | Task 12 test |
| Windows present but every lane empty | Valid analysis | Snapshot with zero candidates; metrics `ABSENT`; no zero inference | Task 8/12 tests |
| One evidence lane only | Candidates below the two-lane rule | `fragmented` status; metrics `PARTIAL`; `lane_presence` records the absence | Task 4/8 tests |
| Person holds two tokens in one lane | Overlap preserved | Two candidates; person listed in `overlap_person_ids` | Task 4 test |
| Member's self-identification cluster is assigned to another candidate | No forced merge | Candidate `contested`; membership `contested` | Task 4 test |
| Candidate exceeds 512 members | Deterministic truncation, no silent loss | Member list truncated with `provenance_code="member_list_truncated"` | Task 12 test |
| Snapshot exceeds 4 MiB or 4096 candidates | No publication | `macro_society_size_limit` | Task 10 test |
| Duplicate publication id with different bytes | Existing publication untouched | `macro_society_publication_exists` | Task 13 test |
| `PALIMPSEST_MACRO_SOCIETY_ROOT` unset | API state unset | 503 `macro_society_disabled`; CLI receipt `disabled` | Task 14/15 tests |
| Cursor reused with a changed filter or publication | No page served | 400 `macro_society_cursor_invalid`; expired 410 | Task 14 test |
| Required Compose/browser lane with a missing prerequisite | No green certification | Recorded `unexecuted` with prerequisite | Task 18/20 |

## Architecture and Decisions

1. **Analysis-only authority.** The fourteenth context is `detached_analysis`
   with `owner_packages=("analysis",)`, no flag, no reservation, and no world
   seam. A candidate is a label, not an entity.
2. **No new packages.** Work lands in existing bounded packages: `analysis`
   (detection/identity/lineage/metrics), `simulation` (artifact contract),
   `experiments` (bridge), `persistence` (store), `api` (GET adapter),
   `research_runner` (CLI), and the Svelte client. The import-linter graph and the
   thirteen-package boundary are unchanged.
3. **Three layers, three types.** Objective population rows are counts only;
   subjective rows are owner-scoped claims; only analytical rows carry `msoc-`
   ids. Leakage is a hard failure.
4. **Nine lanes, no exclusivity.** Interaction, communication, migration,
   exchange are edge lanes; institution, culture, territory, self-identification,
   collective decision are token lanes. Overlap across lanes and across tokens is
   expected.
5. **Absence is data.** A missing lane is reported through `lane_presence` and
   `PARTIAL`/`ABSENT` availability; it is never coerced to "no society".
6. **Identity is minted once.** `msoc-` ids derive from creation tick, founding
   members, and lane signature at first observation; continuation inherits,
   split children and merge results mint new ids.
7. **Lineage is forward-only.** `continued`, `transformed`, `split`, `merge`,
   `dissolved`, `emerged`; edges are monotone in ticks and validated acyclic.
8. **Deterministic by construction.** Sorted ordering everywhere, canonical JSON
   digests, quantized floats, no `hash()`, no UUID, no wall-clock in domain
   values.
9. **Artifact is independent.** `macro-society-snapshot-v1` is a bounded,
   exact-key document in `simulation`; the analysis layer never imports
   persistence and persistence never imports analysis.
10. **Publication is opt-in and non-interfering.** Completed-run publication
    through `research_runner`; a storage failure changes only the publication
    receipt, never scientific status.
11. **Read-only presentation.** `/v1` GET routes with `SUBJECTIVE_DEBUG` and a
    Research UI panel that performs no client-side derivation.
12. **No capacity or prevalence claim.** The benchmark lane measures the
    documented caps only; "candidate count" is an analytical count under stated
    coverage.
13. **Compatibility is additive.** Runner v4/v55/v56, commands 43, observer
    semantic types 73, replay v22, codec v20, Alembic `0017`, `/v1`,
    `observer-protocol-v1`, and the four reserved write pairs are unchanged.
14. **V4-01 is superseded openly.** The 13-context count and
    `v4-context-map-v1` become 14 and `v4-context-map-v2` in Task 1, with the
    V4-01 historical text retained.

### Context declaration

| Context | Flag | Authority | Owning packages | Prerequisites | Existing mechanism | Event strategy |
| --- | --- | --- | --- | --- | --- | --- |
| `macro_society_identity` | — (analysis-only) | detached-analysis | `analysis` | — | candidate-community analysis, cultural/institutional evidence joins, group persistence | reuse |

### Unchanged compatibility pins

Default runner/result `v4`/`v2`; latest feature runner `v55`; accepted runner adds
`v56` only; events `EVENT_SCHEMA_REPLAY_V22`; codec `v20`; commands 43; observer
semantic types 73; metric families 140 (V4-02 change); Alembic `0017`; `/v1`;
`observer-protocol-v1`; observer layout `observer-layout-v1`; four reserved write
pairs (events 23-26 / codecs `v21`-`v24`); `prepare_parallel=False`.
`institutional_economy` and `multi_hop_testimony_tracking` remain unowned and
fail closed.

## Phase Index

1. [Phase 1: Context and Closed Contract](phase-01-context-and-contract.md) — Tasks 1-2
2. [Phase 2: Evidence and Candidate Detection](phase-02-evidence-and-detection.md) — Tasks 3-5
3. [Phase 3: Stable Identity and Split/Merge Lineage](phase-03-identity-and-lineage.md) — Tasks 6-7
4. [Phase 4: Metric Families and Catalog Registration](phase-04-metrics-and-catalog.md) — Tasks 8-9
5. [Phase 5: Snapshot Artifact Contract](phase-05-artifact-contract.md) — Tasks 10-11
6. [Phase 6: Composition and Durable Publication](phase-06-composition-and-persistence.md) — Tasks 12-13
7. [Phase 7: Read-Only API, CLI, and Research UI](phase-07-api-cli-and-ui.md) — Tasks 14-16
8. [Phase 8: Invariants and Regression](phase-08-invariants-and-regression.md) — Tasks 17-18
9. [Phase 9: Documentation and Final Verification](phase-09-documentation-and-verification.md) — Tasks 19-20

## Cross-Phase Dependencies

- Task 2 depends on Task 1: the contract's lane and status vocabulary must match
  the declared context and its non-goals.
- Task 3 depends on Task 2: adapters emit the contract's lane and token types.
- Task 4 depends on Task 3: detection consumes normalized windows.
- Task 5 depends on Task 4: layer projection needs detected candidates and
  `known_person_ids`.
- Task 6 depends on Task 4: identity assignment matches detected candidates.
- Task 7 depends on Task 6: lineage consumes the assignment's accepted pairs.
- Task 8 depends on Tasks 4-7: all four metric families read the analysis object.
- Task 9 depends on Task 8: specs must declare exactly the emitted value keys.
- Task 10 depends on Tasks 7-8: the snapshot schema mirrors analysis records and
  the metric provenance values.
- Task 11 depends on Task 10: paging selects typed records and needs the codec.
- Task 12 depends on Tasks 7 and 11: the bridge needs analysis and the ports.
- Task 13 depends on Task 11: the store implements the ports.
- Task 14 depends on Task 13: the API reads the committed store.
- Task 15 depends on Tasks 12-13: the CLI builds a harvest and publishes it.
- Task 16 depends on Task 14: the panel consumes the four routes.
- Task 17 depends on Tasks 2-16: the suite asserts every authority claim.
- Task 18 depends on Task 17: regression runs only after the invariant gate is
  green.
- Task 19 depends on Tasks 2-18: documentation describes verified surfaces.
- Task 20 depends on Tasks 18-19: final certification needs receipts and docs.

## Tasks

### Phase 1: Context and Closed Contract
- [x] Task 1: Extend the V4 context registry with the macro-society context ([details](phase-01-context-and-contract.md#task-1-extend-the-v4-context-registry-with-the-macro-society-context))
- [x] Task 2: Freeze the closed macro-society analytical contract ([details](phase-01-context-and-contract.md#task-2-freeze-the-closed-macro-society-analytical-contract)) (depends on 1)

### Phase 2: Evidence and Candidate Detection
- [x] Task 3: Normalize detached evidence into analysis windows ([details](phase-02-evidence-and-detection.md#task-3-normalize-detached-evidence-into-analysis-windows)) (depends on 2)
- [x] Task 4: Detect per-lane clusters and compose cross-lane candidates ([details](phase-02-evidence-and-detection.md#task-4-detect-per-lane-clusters-and-compose-cross-lane-candidates)) (depends on 3)
- [x] Task 5: Project objective, subjective, and analytical layers separately ([details](phase-02-evidence-and-detection.md#task-5-project-objective-subjective-and-analytical-layers-separately)) (depends on 4)

### Phase 3: Stable Identity and Split/Merge Lineage
- [x] Task 6: Assign stable analytical IDs across windows ([details](phase-03-identity-and-lineage.md#task-6-assign-stable-analytical-ids-across-windows)) (depends on 4)
- [x] Task 7: Derive split/merge lineage with acyclicity validation ([details](phase-03-identity-and-lineage.md#task-7-derive-splitmerge-lineage-with-acyclicity-validation)) (depends on 6)

### Phase 4: Metric Families and Catalog Registration
- [ ] Task 8: Emit the four macro-society metric documents ([details](phase-04-metrics-and-catalog.md#task-8-emit-the-four-macro-society-metric-documents)) (depends on 4, 5, 7)
- [ ] Task 9: Register four families and raise the catalog to 140 ([details](phase-04-metrics-and-catalog.md#task-9-register-four-families-and-raise-the-catalog-to-140)) (depends on 8)

### Phase 5: Snapshot Artifact Contract
- [ ] Task 10: Define snapshot models and the canonical codec ([details](phase-05-artifact-contract.md#task-10-define-snapshot-models-and-the-canonical-codec)) (depends on 7, 8)
- [ ] Task 11: Add bounded paging and read/publication ports ([details](phase-05-artifact-contract.md#task-11-add-bounded-paging-and-readpublication-ports)) (depends on 10)

### Phase 6: Composition and Durable Publication
- [ ] Task 12: Compose completed-run harvests into snapshots ([details](phase-06-composition-and-persistence.md#task-12-compose-completed-run-harvests-into-snapshots)) (depends on 7, 11)
- [ ] Task 13: Implement the atomic quota-bounded filesystem store ([details](phase-06-composition-and-persistence.md#task-13-implement-the-atomic-quota-bounded-filesystem-store)) (depends on 11)

### Phase 7: Read-Only API, CLI, and Research UI
- [ ] Task 14: Add settings and GET-only API routes ([details](phase-07-api-cli-and-ui.md#task-14-add-settings-and-get-only-api-routes)) (depends on 13)
- [ ] Task 15: Compose the producer in research_runner ([details](phase-07-api-cli-and-ui.md#task-15-compose-the-producer-in-research_runner)) (depends on 12, 13)
- [ ] Task 16: Add the read-only Research UI panel ([details](phase-07-api-cli-and-ui.md#task-16-add-the-read-only-research-ui-panel)) (depends on 14)

### Phase 8: Invariants and Regression
- [ ] Task 17: Add the macro-society boundary and determinism suite ([details](phase-08-invariants-and-regression.md#task-17-add-the-macro-society-boundary-and-determinism-suite)) (depends on 2-16)
- [ ] Task 18: Execute the full V1-V4 regression and qualification lanes ([details](phase-08-invariants-and-regression.md#task-18-execute-the-full-v1-v4-regression-and-qualification-lanes)) (depends on 17)

### Phase 9: Documentation and Final Verification
- [ ] Task 19: Execute the mandatory documentation checkpoint ([details](phase-09-documentation-and-verification.md#task-19-execute-the-mandatory-documentation-checkpoint)) (depends on 2-18)
- [ ] Task 20: Perform final V4-02 verification ([details](phase-09-documentation-and-verification.md#task-20-perform-final-v4-02-verification)) (depends on 18, 19)

## Commit Plan

Proposed implementation checkpoints; no commit is made by planning.

1. After Tasks 1-2: `feat(v4): declare the macro-society analytical context and contract`
2. After Tasks 3-5: `feat(v4): detect overlapping macro-society candidates from detached evidence`
3. After Tasks 6-7: `feat(v4): assign stable macro-society identities and split/merge lineage`
4. After Tasks 8-9: `feat(v4): add macro-society metric families`
5. After Tasks 10-13: `feat(v4): publish bounded macro-society snapshots`
6. After Tasks 14-16: `feat(v4): serve read-only macro-society views`
7. After Tasks 17-20: `test(v4): enforce macro-society invariants and regression`

## Blocking Conditions and Non-Goals

- Adding a capability flag, runner schema (`v57`), command, event, observer
  semantic type, `/v2` route, `observer-protocol-v2` serving, or SQL migration to
  make this plan work is a blocking scope violation. Stop and re-plan.
- Creating an objective Country, Nation, Civilization, Government, Polity, Tribe,
  Empire, State, or any global organization/society registry is forbidden. The
  only identity is an analysis-local `msoc-` id.
- Giving `WorldEngine`, cognition, memory, prompts, admission, or stop selectors
  any read of a macro-society candidate is forbidden.
- Requiring exclusive membership, forcing self-identification, or treating a
  candidate as a census is forbidden.
- Claiming capacity, prevalence, emergence probability, or predictive power is
  forbidden. The benchmark lane measures documented caps only.
- Editing `.ai-factory/ROADMAP.md` or closing M8 is out of scope;
  `$aif-roadmap` owns that.
- Changing the Godot client or observer protocol is out of scope; the Research UI
  is the only client change.
- Weakening an existing pin or assertion (catalog counts, Alembic `0017`, replay
  v22, codec v20, command count, observer semantic count) is forbidden. The only
  intentional pin changes are 136 → 140 metric families, 13 → 14 V4 contexts, and
  `v4-context-map-v1` → `v4-context-map-v2`.
- Full qualification requires a disposable PostgreSQL/pgvector instance, Docker,
  a real browser driver, and the pinned Node/pnpm and Godot toolchains. A missing
  prerequisite leaves the lane unexecuted and blocks certification; it never
  becomes a skip-pass.
- Do not implement any other V4 context (`organizations`, `formal_rules`,
  `legal_disputes`, `diplomacy`, `organized_conflict`,
  `infrastructure_networks`, `supply_chains`, `markets_credit`, `science`,
  `epidemics`, `ecological_feedback`, `disasters`, `societal_resilience`) in
  this plan.

## Definition of Done

- All 20 indexed tasks have verified completion evidence; only this index holds
  task progress checkboxes.
- The V4 registry validates at 14 contexts with `v4-context-map-v2`, exactly one
  additional analysis-only context, and the four reserved write pairs unchanged.
- Nine evidence lanes are derived from existing detached sources; no new event,
  command, ledger, route version, flag, or migration exists.
- Candidates support overlap, disputed membership, fragmentation, and absent
  self-identification; exclusive `society_emergence@1` behavior is unchanged.
- `msoc-` identities are minted from creation evidence, stable under churn, and
  never derived from a mutable counter or world state.
- Lineage records `continued`, `transformed`, `split`, `merge`, `dissolved`, and
  `emerged` edges that are forward-only, acyclic, and deterministic.
- Objective population structure, subjective identity claims, and analytical
  candidates are three distinct types with passing leakage tests.
- The metric catalog is exactly 140 with four appended families and no change to
  existing families.
- `macro-society-snapshot-v1` is canonical, bounded, immutable after publication,
  and served through opt-in completed-run publication.
- Four GET-only `/v1` routes require `SUBJECTIVE_DEBUG`, have an explicit disabled
  state, and are consumed by a read-only Research UI panel.
- The boundary suite proves analysis-only authority, absence of magic actors, no
  world imports, no flags, and no observer or migration change.
- The full V1-V4 regression lanes and static gates execute and pass; any
  unexecuted required lane is reported with its blocker and is not certified.
- Documentation states what a macro-society is, what it is not, and how identity
  and lineage are formed, with every count matching the code.
