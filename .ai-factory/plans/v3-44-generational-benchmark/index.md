<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V3-44 End-to-End Generational Civilization Benchmark

Mode: ultra
Branch: main (remain on current branch; `git.create_branches: false`)
Created: 2026-10-27
Improved: 2026-10-27 (`$aif-improve`; six approved refinements; task IDs/statuses preserved)
Plan identifier: `v3-44-generational-benchmark`
Status: implementation in progress; Tasks 1–16 complete (Task 15 DB gate and Godot baseline verified). Task 17 is partially implemented: the source-pinned marker manifest, a 160-tick visual fixture and sparse opportunity schedule now run to completion, and a real communication bug (duplicate rendered concepts) was fixed. The current fixture covers 4 of 8 markers (new agents, deaths, migration, collective project); teaching, technology spread, cultural differentiation and office succession still need additional ordinary-command opportunities before Godot/browser acceptance can be claimed.

## Original Request

v3-44 V3 end-to-end generational civilization benchmark

Plan naming requirement:

The final plan artifact MUST use a canonical stem beginning with `v3-`.

Suggested stem:

v3-44-generational-benchmark

Create the final V3 integration and research benchmark suite.

Run all V1 and V2 regression suites.

Create multiple deterministic/small-statistical scenarios rather than one giant scripted demo.

Include scenarios covering:

1. New agents entering a society without inherited memories.
    
2. Dependent young agents requiring social care.
    
3. Intergenerational skill transmission.
    
4. Cultural knowledge mutating across generations.
    
5. Eyewitness memory becoming communicative memory and later cultural memory.
    
6. A written record preserving information after all witnesses die.
    
7. A false written record preserving misinformation.
    
8. Technology discovery.
    
9. Technology diffusion.
    
10. Technology loss after all knowledge holders disappear.
    
11. Independent technology rediscovery.
    
12. Emergent inheritance practices after a death.
    
13. Long-term promise/debt fulfillment and violation.
    
14. Negotiated barter with subjective valuations.
    
15. Candidate medium-of-exchange behavior without hard-coded money.
    
16. Collective project coordination.
    
17. Public-good contribution/free-riding patterns.
    
18. Migration between regions.
    
19. Two isolated populations developing different cultural patterns.
    
20. Re-contact and knowledge/cultural exchange.
    
21. Symbolic vocabulary divergence.
    
22. Semantic drift across generations.
    
23. Cross-cultural mistranslation.
    
24. Historical narrative surviving after eyewitness extinction.
    
25. Emergence of a persistent social role.
    
26. Succession of an office after its occupant dies.
    
27. Institutional persistence across generations.
    
28. Institutional decay or disappearance.
    
29. Same initial world with a small founder-event intervention creating divergent histories.
    
30. A multi-generation forked replay experiment.
    

### Scientific constraints

Do not assert:

a government must emerge

money must emerge

religion must emerge

a myth must emerge

an institution must emerge

Instead validate:

mechanisms exist

events remain correctly sourced

provenance is preserved

emergence can be measured when it occurs

null results remain valid research outcomes

### Generational invariants

Verify:

new agents never inherit arbitrary parent memories

agents cannot access objective historical truth unless perceived through valid channels

dead agents stop acting

records persist only through physical world mechanisms

records may contain false information

technology can be lost

knowledge lineage remains auditable

institutional roles remain subjective/social constructs

objective possession remains separate from legitimacy beliefs

multiple societies do not magically share knowledge

migration occurs through WorldEngine actions

presentation coordinates never enter simulation semantics

Godot observer remains read-only

### Replay invariants

Verify:

multi-generation deterministic replay works

birth/new-agent creation replays identically

death replays identically

genealogy reconstructs identically

technology lineage reconstructs identically

forked historical experiments preserve parent/child run lineage

recorded LLM cognition can be replayed where configured

### Visualization acceptance

Verify the zero-install release workflow still requires only:

container runtime

browser

and does NOT require:

local Godot installation

Godot editor

manual Web export

manual frontend build

Validate that Godot can visually replay a multi-generation scenario containing:

new agents  
deaths  
migration  
teaching  
collective project  
technology spread  
cultural divergence  
institutional succession

### Research UI acceptance

Verify researchers can inspect:

genealogy  
knowledge lineage  
technology history  
cultural evolution  
historical narratives  
institutions  
migration  
population  
forked historical runs

### V3 completion criteria

V3 is complete when:

- V1 and V2 invariants remain valid.
    
- Population can change across time.
    
- Multiple generations can coexist and replace one another.
    
- New agents learn culture rather than receiving copied memories.
    
- Knowledge can persist beyond individual lifetimes.
    
- Knowledge can also be lost.
    
- Technologies can emerge, spread, mutate and disappear.
    
- Cultural traits can be measured across generations.
    
- Separate populations can culturally diverge.
    
- Populations can later interact without magically synchronizing knowledge.
    
- Persistent social roles/institutions can be observed without scripting their existence.
    
- Institutions can survive occupant death.
    
- Institutions can transform or disappear.
    
- Historical narratives may outlive all witnesses.
    
- Small historical interventions can be compared through forked multi-generation runs.
    
- Godot can observe generational history without affecting it.
    
- Research UI can analyze lineage and long-term societal change.
    
- Normal deployment remains zero-install with respect to Godot.
    
- Long-running generational experiments remain reproducible and scientifically auditable.

## Settings

- Testing: yes; all requested regression/invariant/replay/client gates, coverage enabled.
- Logging: verbose metadata-only; bounded DEBUG flow/counts, INFO milestones, WARN incomplete evidence and ERROR safe codes. `PALIMPSEST_LOG_LEVEL` controls operational verbosity; no private content, payload surrogates, prompts, credentials or DSNs.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 23.
- Language: English UI/artifacts; preserve technical terms.
- Git: enabled; base `main`; no branch/worktree creation; skip-push preference retained. Commit checkpoints below are suggestions, not authorization to commit during planning.
- Workflow: slug IDs; normal verification, with explicit complete required-gate certification.
- Naming: canonical stem `v3-44-generational-benchmark`; phase filenames also start with `v3-`. `index.md` is the canonical ultra entrypoint.
- Research source: no configured RESEARCH file or marked research bundle exists; no external research conclusions are invented.
- Execution: planning only in this invocation. All proposed module/type/CLI/schema names are new unless identified as existing in phase evidence tables.

## Roadmap Linkage

Milestone: "M7 — V3 Generational Civilization"
Rationale: Integrate and qualify the existing V3 mechanisms, generational research, replay and read-only release surfaces without scripting civilizational outcomes.

M7 remains open for unowned `institutional_economy` and deferred kinship cultural/knowledge handoff; M6 remains open for `multi_hop_testimony_tracking`. This plan does not implement or claim those capabilities. Closing this suite is not automatic roadmap closure; use the milestone owner workflow/user decision.

## Requirements Reconciliation

Authority: repository/project rules constrain all edits; the Original Request defines scope. Existing architecture, exact codecs and scientific contracts govern compatibility. The request's positive scenario descriptions are refined by its explicit null-result constraints: mechanism/provenance tests are mandatory; autonomous emergence and effect direction are not. No conflicting source is silently rewritten.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| Separate V3 30-case registry, preserve V2 16-case registry and V1 A–E/reference gates | Original Request; `src/experiments/benchmark_suite.py`; `docs/v2-benchmark-suite.md` | Tasks 1, 21: exact registry pins and whole default/integration/Compose/client collections |
| Controlled mechanism fixtures may schedule normally admitted commands, but cannot seed subjective state or count as autonomous emergence | Original Request Scientific constraints; `src/experiments/interventions.py` | Tasks 4, 6–13: applied acknowledgements, intervention receipts, arbiter-free independent research; grouped research retains declared treatment controls |
| Every actual newborn store is measured before first cognition; modes are not inherited content | Original Request scenarios 1–4; `src/simulation/new_agent_initialization.py`; runner's existing synthetic-zero assertion | Tasks 3–4, 6, 14: real measured snapshots and poisoned-store negative test |
| Descendant symbolic/translation/institution modes need an explicit content-empty profile, not silently expanded old packs | Existing `species_defaults_for` packs; Original Request scenarios 21–28 | Task 3 v55-only new policy ID; old-pack canonical parity; no new runner schema/flag |
| v55 must preserve selected exact lower-family root, not concatenate all historical builder JSON | `src/experiments/generational_execution.py`; `src/simulation/runner_serialization.py` | Tasks 2, 6–13: all recipe codec round-trips and exact prerequisite checks |
| Declared tick horizons require explicitly disabled competing stop selectors; nonfailure early stop is not full coverage | `GenerationalRunSpec`; comparison base cap 6 and BN smoke cap 16 | Tasks 2, 13, 22: no inherited generation/extinction/threshold/criteria cutoffs; actual final boundary equals H |
| Founder-mode changes do not disable the same modes in newborn profiles | `src/simulation/runner.py` `_sync_mid_run_population_entries` / `species_defaults_for` | Tasks 2–3, 12, 22: actual founder/entrant mode vectors, scoped estimands and composite-profile labels |
| Truth labels stay analysis-only; false record marks are physically legal | Original Request scenarios 5–7; `src/experiments/interventions.py` StoryTruthSpec; architecture trust boundary | Tasks 7, 14: real inscription/reading/death plus missing/destroyed/false controls |
| Complete-empty inventory differs from unknown/disabled/truncated capture | `docs/cultural-evolution-metrics.md`; `docs/lineage-explorer.md` | Tasks 4–5, 8, 12: required coverage per selector/arm, censored loss/collapse |
| Objective replay does not reconstruct absent subjective technology lineage | Original Request Replay invariants; `src/simulation/replay.py`; lineage capture contracts | Task 15 separately proves objective fold, deterministic rerun, in-process fork and source-backed lineage rebuild |
| Terminal research inspection must not depend on a terminal-ineligible fork checkpoint | `src/simulation/runner.py` `export_finalized_research_boundary` currently delegates to `capture_fork_checkpoint` | Tasks 4, 13, 15: terminal-safe projection after finish; pending-finalization rejection; strict fork guard preserved |
| True grouped forks require common prefix and complete process-local owner state | `docs/historical-contingency.md`; `src/experiments/path_dependence_catalog.py` | Tasks 13, 15: parent unchanged, same-identity twin, qualified children, process-loss limits |
| Recorded cognition replay is independent from recorded-LLM fork continuation, which remains unsupported | Original Request "where configured"; `SimulationRunner.from_fork_checkpoint` guard | Task 16 whole configured stage/run recording replay, positive usage and zero fallback; recorded forks reject |
| Archival recording usage rejects untracked custom provider factories | `RunnerDependencyFactories.with_generational_control`; `_default_provider` / `_inner_provider_for_recording` | Task 16 uses normal provider/store construction, RECORD not-required versus REPLAY required provenance, positive archived usage and custom-factory rejection |
| Source revision alone is not a clean-source assertion or source-artifact identity | `src/experiments/generational_artifacts.py` `source_identity_preflight` | Tasks 5, 19–20, 22: explicit revision plus exactly one clean/digest assertion, verified image labels, missing/dirty/no-Git tests |
| Positive visual acceptance must use source-backed real history, never substitute mocked evidence or mandate autonomous institutions | Original Request Visualization acceptance and Scientific constraints | Tasks 17, 20: one controlled real fixture, eight actual markers, separately labeled synthetic rendering tests and null research |
| Release image must include Research UI as well as Godot; no host asset build | Original Request zero-install requirements; `Dockerfile`; `compose.yaml` | Tasks 19–20 clean image-only startup and real browser workflows |
| Researchers inspect populated evidence, not only headings/unavailable states | Original Request Research UI acceptance; current `acceptance.test.ts` and browser suite | Tasks 18, 20: actual rows/edges, nine domains, fork comparison, history navigation and negative credential tests |
| Release Research UI checks cannot require host `dist` or unauthenticated external matrix setup | `tests/compose/test_research_ui_wiring.py` local-DIST guard and external matrix GET | Tasks 19–21: authenticated test-owned image stack, real V2 matrix summary, missing host output irrelevant |
| Small-statistical inference uses distinct numeric seed blocks and predeclared comparisons, no positive effect gate | Original Request nulls; cultural/path-dependence comparison contracts | Task 22 zero-difference and missing-pair tests, five fixed seeds, pointwise qualified intervals |
| V3 completion qualification does not own deferred flags or expand measured scale limits | `.ai-factory/ROADMAP.md` M6/M7; `docs/long-horizon-scalability.md` Verified Envelope | Tasks 22–23 completion matrix lists unowned slots, verified 10k and incomplete 100k separately |

### Supported combinations and availability transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| Independent mechanism lane, valid bounded schedule | v55 config + recipe + normal journal + applied/rejected override receipts | Controlled mechanism checks; no forced research conclusion | Tasks 4, 6–12 |
| Independent research cases 01–28, no schedule/arbiter | Same setup identities; ordinary cognition + sources | Unassisted detected/not-detected/unknown outcomes; null allowed | Tasks 4, 22 |
| Grouped cases 29–30, eligible prefix, deterministic fake, mechanism or research lane | BN design/prefix controls/assigned treatment/parent/child/outcome artifacts + actual capture | `grouped_intervention`, not unassisted; independent ordinary-command children; unchanged parent | Tasks 13, 22 |
| Grouped case sent through independent executor or recorded/live provider | No execution/publication | Fail-closed preflight, no fabricated children | Tasks 4, 13, 16 |
| New learner pack on v55 with exact prerequisite specs | Creation policy identity and empty owner state | Fresh learning modes only; later learning through ordinary sources | Tasks 2–4 |
| New learner pack on older schema / missing prerequisites | No admitted invalid configuration | Reject; old packs unchanged | Task 3 |
| Founder-mode contrast with a shared newborn profile | Actual founder and first-entrant mode vectors; declared `founder_roster` scope | Direct estimates use fixed founders' eligible lifetime windows; entrants are not falsely labeled disabled | Tasks 2–3, 12, 22 |
| Different initializer packs across arms | Per-arm creation/profile identities and enumerated mode differences | Explicit `initializer_profile` / `composite_profile` treatment, not isolated single-mode effect | Tasks 2–3, 22 |
| Capture off/on/failed/quota-exhausted | None or immutable bounded source evidence; science unaffected | Disabled/complete/partial/unavailable distinct; missing required evidence blocks acceptance | Tasks 4–5, 14 |
| Complete no phenomenon versus incomplete search | Empty result with complete window versus censored source | `not_detected` versus `unknown`; only complete evidence can prove absence/loss | Tasks 5, 8, 12, 22 |
| Valid addressed/visible learning versus no-contact or foreign-owner source | Fresh owner trace/revision or no uptake | No copying/history download; provenance retained | Tasks 6–12, 14 |
| Deterministic-fake objective replay versus captured subjective lineage | Objective journal versus independent owner capture | Separate qualified parity receipts; no invented subjective fold | Task 15 |
| Fully finalized terminal research read versus pending/aborted-incomplete boundary | Detached finished-stage projection or explicit refusal | Exact terminal H can be inspected without weakening checkpoint guards; unavailable probe does not alter science | Tasks 4, 13, 15 |
| Independent recording available versus miss/schema/component drift | Verified recording references/usage or safe failure | Offline exact reproduction or fail closed, no live fallback | Task 16 |
| Inspection/debug credentials valid/absent/revoked; capture complete/partial | No client writer or truth backchannel | Existing auth/availability and snapshot-pinned reads; no private-data leaks | Tasks 18, 20 |
| All required regression/browser/DB gates executed versus missing prerequisite | Per-gate counts/results | Certified only if required gates pass; missing gate stays unexecuted | Tasks 20–23 |
| Valid revision plus clean/digest assertion versus missing/conflicting source metadata | Same explicit source identity across archive/grouped/report/image producer | Valid no-Git container execution or preflight rejection; never invented source cleanliness | Tasks 5, 19–20, 22 |
| Completed 10k versus incomplete 100k stress attempt | Actual counts/boundaries/budgets, immutable sources | Qualified measured-through claim only; never universal capacity | Task 22 |

## Architecture and Decisions

1. **Separate registry and outer composition.** New `experiments.civilization_benchmark_*` modules own immutable specs, recipes, evidence checks and report composition; `research_runner` owns SQL/filesystem/provider adapters and CLI. Simulation never imports benchmark/analysis/API/persistence. No private world imports, new HTTP routes or client authority.
2. **Thirty small cases, two lanes.** Each requested scenario has a stable ID and controlled valid-channel mechanism lane. Independent cases 01–28 have autonomous research lanes; grouped cases 29–30 have explicitly intervention-based research lanes retaining the predeclared prefix controls/treatments. Shared worlds reduce duplication, not requirement coverage. All results keep execution, invariants, mechanism coverage, measurement, phenomenon, publication and comparison separate.
3. **No scripted knowledge or institutional state.** Physical setup, laws, resources and bounded command interventions are declared experiments. No preloaded parent memories, global vocabulary, technology/office registries or objective legitimacy. Policy-level synthetic positive detector tests are labeled and never substituted for real trajectory evidence.
4. **Explicit learner profile.** Add one v55-only versioned, opt-in, empty-content species pack for descendant modes; keep all old packs unchanged. This is the only deliberate new scientific configuration policy identifier; defaults and capability ownership stay unchanged.
5. **Finite predeclared budgets.** Smoke: seed 23, 96 ticks, four founders, interval 8/generation 16/lifespan 24/cap 12. Research: seeds 11/23/37/53/71, 192 ticks, same base policy. Case 30 declares faster cohort labels (interval 2/generation 4) and F=12. Visual: seed 23, 160 ticks, six founders/cap 16. Set generation cap/threshold to none, extinction stop false and custom stop criteria empty; ordinary runtime-terminal stopping remains disabled. Full lanes must actually reach H. Profiles are fixtures, not capacity claims. No seed hunting or posthoc horizon extension.
6. **Reuse exact scientific contracts.** Existing cultural families and BN seven-domain estimators supply measurements. New strict benchmark run/suite sibling schemas do not alter runner/result/archive logical schemas or catalog family counts. Existing root spec/mode validators remain authoritative.
7. **Replay guarantees stay distinct.** Objective creation/death/genealogy/physical record replay, deterministic full rerun, process-local supported subjective fork continuation and captured lineage rebuild are separately proven. Full durable subjective restart and recorded/live LLM forks are not promised.
8. **Source-backed release acceptance.** One bounded controlled visual history covers the eight requested displays. Thirty independent small cases remain the scientific suite. Source-backed positive visual markers do not force an emergence finding; if unavailable, that positive visual acceptance is blocked rather than fabricated.
9. **Zero-install for users, not build machines.** The image builds Godot Web and the Svelte SPA internally; runtime is non-root, without editor/Node tooling. End users pull/run and browse; CI may use pinned Godot/pnpm/Playwright. `/research/` mounts before Godot `/`; debug/capture remain opt-in.
10. **Qualified completion, not slogan.** Full suite certification needs executed required gates, not skips. Measured scale and deferred ownership remain explicit. No M6/M7 milestone is closed by this plan itself.
11. **Scoped effects and source attestations.** Per-agent mode contrasts are founder-roster-scoped with unchanged entrant packs; initializer-pack differences are composite treatments. Explicit source revision plus exactly one verified clean/digest assertion accompanies every run, including image-owned producers without Git. Image-only UI checks use authenticated real matrix sources and no host frontend output.

### Unchanged compatibility pins

Default runner/result v4/v2; latest feature runner v55; commands 43; observer semantic types 73; metric families 136; feature-selected replay-v22/codec-v20; Alembic 0017; `/v1`; `observer-protocol-v1`; `prepare_parallel=False`. V2 benchmark count remains 16. Unowned `institutional_economy` and `multi_hop_testimony_tracking` continue failing closed.

## Scenario Coverage

All IDs below have prefix `v3-bench-`. Phase tables define required sources, controlled checks, autonomous outcomes and controls.

| Request # | ID suffix | Detailed task |
| --- | --- | --- |
| 1 | `01-blank-slate` | 6 |
| 2 | `02-dependent-care` | 6 |
| 3 | `03-intergenerational-teaching` | 6 |
| 4 | `04-cultural-mutation` | 6 |
| 5 | `05-memory-layers` | 7 |
| 6 | `06-record-after-witnesses` | 7 |
| 7 | `07-false-record` | 7 |
| 8 | `08-technology-discovery` | 8 |
| 9 | `09-technology-diffusion` | 8 |
| 10 | `10-technology-loss` | 8 |
| 11 | `11-technology-rediscovery` | 8 |
| 12 | `12-inheritance-practices` | 9 |
| 13 | `13-long-term-commitments` | 9 |
| 14 | `14-subjective-barter` | 9 |
| 15 | `15-candidate-exchange-medium` | 9 |
| 16 | `16-collective-project` | 10 |
| 17 | `17-public-good-patterns` | 10 |
| 18 | `18-regional-migration` | 10 |
| 19 | `19-isolated-divergence` | 10 |
| 20 | `20-recontact-exchange` | 10 |
| 21 | `21-vocabulary-divergence` | 11 |
| 22 | `22-generational-semantic-drift` | 11 |
| 23 | `23-cross-cultural-mistranslation` | 11 |
| 24 | `24-narrative-after-witnesses` | 12 |
| 25 | `25-persistent-role` | 12 |
| 26 | `26-office-succession` | 12 |
| 27 | `27-institutional-persistence` | 12 |
| 28 | `28-institutional-decay` | 12 |
| 29 | `29-founder-contingency` | 13 |
| 30 | `30-multigeneration-fork` | 13 |

### Completion criteria traceability

| Requested completion criterion | Required evidence/tasks |
| --- | --- |
| V1/V2 invariants remain valid | 14, 21: full regression collections, not only named gates |
| Changing population; coexisting/replacing generations | 2, 6, 15: actual admissions/deaths/cohort boundaries and replay |
| New agents learn culture, not copied memories | 3–4, 6–7, 14: measured blank state and later valid sources |
| Knowledge persists beyond lifetimes and can be lost | 7–8: witness extinction, physical record reading, complete holder/archive loss |
| Technology emerges/spreads/mutates/disappears | 8: experimentation, actual practical-knowledge acquisition/mutation/recombination parentage and lifecycle evidence; cultural-trait mutation alone is insufficient; observed nulls allowed |
| Cultural traits measured across generations | 6, 11–12, 22: retained cultural inventories and existing families/seed-block estimands |
| Isolated populations can diverge and re-contact without synchronization | 10–11: exposure separation, ordinary journeys and fresh recipient uptake |
| Persistent social roles/institutions observed without scripted existence | 12, 22: owner-local policies, independent evidence, autonomous runs and null-capable detection |
| Institutions survive occupant death, transform or disappear | 12, 15: role identity, succession, memory/decay and complete/censored windows |
| Narratives may outlive witnesses | 7, 12: actual extinction and later sourced owner narrative |
| Small interventions compared through multi-generation forks | 13, 15, 22: common prefix, children, no-op twin, predeclared seed blocks |
| Godot observes without affecting history | 14, 17, 20: coordinate/read noninterference and actual Web replay |
| Research UI analyzes lineage and long-term change | 18, 20: nine populated domains, qualified sources, real history/fork navigation |
| Normal deployment is zero-install with respect to Godot | 19–20: image-only runtime/browser, no host export/build |
| Long-running reproducibility and scientific auditability | 5, 15–16, 22–23: immutable manifests, recording/replay, real scale envelopes and complete source references |

## Phase Index

1. [Phase 1: Contracts and composition](v3-44-phase-01-contracts.md) — Tasks 1–3
2. [Phase 2: Execution and artifacts](v3-44-phase-02-execution.md) — Tasks 4–5
3. [Phase 3: Population and memory](v3-44-phase-03-population-and-memory.md) — Tasks 6–7
4. [Phase 4: Technology and exchange](v3-44-phase-04-technology-and-exchange.md) — Tasks 8–9
5. [Phase 5: Regions and language](v3-44-phase-05-regions-and-language.md) — Tasks 10–11
6. [Phase 6: Institutions and forks](v3-44-phase-06-institutions-and-forks.md) — Tasks 12–13
7. [Phase 7: Invariants and replay](v3-44-phase-07-invariants-and-replay.md) — Tasks 14–16
8. [Phase 8: Presentation and release](v3-44-phase-08-presentation-and-release.md) — Tasks 17–20
9. [Phase 9: Qualification](v3-44-phase-09-qualification.md) — Tasks 21–23

## Cross-Phase Dependencies

- Tasks 1→2→3 establish registry, valid atomic configurations and empty descendant modes. Task 4 depends on all three; Task 5 depends on 4.
- Tasks 6–7 depend on 1–5. Task 7 additionally reuses Task 6's witness/entry probes.
- Task 8 depends on 6–7 for firsthand acquisition/record loss; Task 9 depends on 4–5 and actual death/learning probes from 6–8.
- Task 10 depends on 6–9 for actual skill/knowledge/physical exchanges; Task 11 depends on 10 and the new profile (3).
- Task 12 depends on 7 and 10–11; Task 13 depends on the execution/artifact framework (4–5) and source projections proven through 12.
- Task 14 depends on implemented cases 6–13; Task 15 depends on 14 and the real artifact sources; Task 16 depends on 4–5 and 15's comparison oracle.
- Task 17 depends on 6–16; Task 18 depends on 5, 12–16. Task 19 uses existing client build inputs and can begin after 1, but is not complete until integration tests verify the package. Task 20 requires 17–19 and production artifact publishers.
- Task 21 requires completed implementation/client phases; Task 22 requires 21 and retained real gate evidence; Task 23 requires 22. Execute numeric order by default; no task may be marked complete before its dependencies' required evidence exists.

## Tasks

### Phase 1
- [x] Task 1: Define the executable thirty-scenario registry ([details](v3-44-phase-01-contracts.md#task-1-define-the-executable-thirty-scenario-registry))
- [x] Task 2: Build bounded and comparable v55 benchmark worlds ([details](v3-44-phase-01-contracts.md#task-2-build-bounded-and-comparable-v55-benchmark-worlds)) (depends on 1)
- [x] Task 3: Add an explicit blank civilization learner profile ([details](v3-44-phase-01-contracts.md#task-3-add-an-explicit-blank-civilization-learner-profile)) (depends on 1, 2)

### Phase 2
- [x] Task 4: Execute independent lanes with real owner and admission probes ([details](v3-44-phase-02-execution.md#task-4-execute-independent-lanes-with-real-owner-and-admission-probes)) (depends on 1, 2, 3)
- [x] Task 5: Publish reproducible sibling reports and a bounded CLI ([details](v3-44-phase-02-execution.md#task-5-publish-reproducible-sibling-reports-and-a-bounded-cli)) (depends on 4)

### Phase 3
- [x] Task 6: Exercise blank entry, care, teaching and cultural mutation ([details](v3-44-phase-03-population-and-memory.md#task-6-exercise-blank-entry-care-teaching-and-cultural-mutation)) (depends on 1, 2, 3, 4, 5)
- [x] Task 7: Exercise memory layers and true or false surviving records ([details](v3-44-phase-03-population-and-memory.md#task-7-exercise-memory-layers-and-true-or-false-surviving-records)) (depends on 6)

### Phase 4
- [x] Task 8: Exercise discovery, diffusion, loss and independent rediscovery ([details](v3-44-phase-04-technology-and-exchange.md#task-8-exercise-discovery-diffusion-loss-and-independent-rediscovery)) (depends on 6, 7)
- [x] Task 9: Exercise inheritance claims, delayed commitments, barter and exchange functions ([details](v3-44-phase-04-technology-and-exchange.md#task-9-exercise-inheritance-claims-delayed-commitments-barter-and-exchange-functions)) (depends on 4, 5, 6, 7, 8)

### Phase 5
- [x] Task 10: Exercise collective work, public goods, migration and re-contact ([details](v3-44-phase-05-regions-and-language.md#task-10-exercise-collective-work-public-goods-migration-and-re-contact)) (depends on 6, 7, 8, 9)
- [x] Task 11: Exercise vocabulary divergence, semantic drift and mistranslation ([details](v3-44-phase-05-regions-and-language.md#task-11-exercise-vocabulary-divergence-semantic-drift-and-mistranslation)) (depends on 3, 10)

### Phase 6
- [x] Task 12: Exercise narrative survival, roles, succession, persistence and decay ([details](v3-44-phase-06-institutions-and-forks.md#task-12-exercise-narrative-survival-roles-succession-persistence-and-decay)) (depends on 7, 10, 11)
- [x] Task 13: Execute founder perturbations and multigeneration grouped forks ([details](v3-44-phase-06-institutions-and-forks.md#task-13-execute-founder-perturbations-and-multigeneration-grouped-forks)) (depends on 4, 5, 12)

### Phase 7
- [x] Task 14: Gate all generational scientific invariants ([details](v3-44-phase-07-invariants-and-replay.md#task-14-gate-all-generational-scientific-invariants)) (depends on 6, 7, 8, 9, 10, 11, 12, 13)
- [x] Task 15: Qualify objective replay and captured subjective lineage separately ([details](v3-44-phase-07-invariants-and-replay.md#task-15-qualify-objective-replay-and-captured-subjective-lineage-separately)) (depends on 14)
- [x] Task 16: Replay recorded LLM cognition in a real independent generational run ([details](v3-44-phase-07-invariants-and-replay.md#task-16-replay-recorded-llm-cognition-in-a-real-independent-generational-run)) (depends on 4, 5, 15)

### Phase 8
- [ ] Task 17: Replay one real multi-generation visual fixture in Godot ([details](v3-44-phase-08-presentation-and-release.md#task-17-replay-one-real-multi-generation-visual-fixture-in-godot)) (depends on 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16)
- [ ] Task 18: Inspect populated evidence and fork history in the Research UI ([details](v3-44-phase-08-presentation-and-release.md#task-18-inspect-populated-evidence-and-fork-history-in-the-research-ui)) (depends on 5, 12, 13, 14, 15, 16)
- [ ] Task 19: Ship both Web clients in the normal release image ([details](v3-44-phase-08-presentation-and-release.md#task-19-ship-both-web-clients-in-the-normal-release-image)) (depends on 1)
- [ ] Task 20: Gate release on authenticated real-browser benchmark acceptance ([details](v3-44-phase-08-presentation-and-release.md#task-20-gate-release-on-authenticated-real-browser-benchmark-acceptance)) (depends on 17, 18, 19)

### Phase 9
- [ ] Task 21: Execute all V1 and V2 regression lanes without silent skips ([details](v3-44-phase-09-qualification.md#task-21-execute-all-v1-and-v2-regression-lanes-without-silent-skips)) (depends on 14, 15, 16, 17, 18, 19, 20)
- [ ] Task 22: Run deterministic smoke and predeclared small-statistical research qualification ([details](v3-44-phase-09-qualification.md#task-22-run-deterministic-smoke-and-predeclared-small-statistical-research-qualification)) (depends on 21)
- [ ] Task 23: Document the qualified V3 completion contract and perform final verification ([details](v3-44-phase-09-qualification.md#task-23-document-the-qualified-v3-completion-contract-and-perform-final-verification)) (depends on 22)

## Commit Plan

Proposed implementation checkpoints; no commit is made by planning.

1. After Tasks 1–3: `feat(experiments): define V3 benchmark contracts and blank learner policy`
2. After Tasks 4–5: `feat(research): execute and verify generational benchmark artifacts`
3. After Tasks 6–7: `test(v3): cover population learning and historical memory channels`
4. After Tasks 8–9: `test(v3): cover technology continuity and subjective exchange`
5. After Tasks 10–11: `test(v3): cover coordination migration and language divergence`
6. After Tasks 12–13: `test(v3): cover subjective institutions and grouped historical forks`
7. After Tasks 14–16: `test(v3): enforce generational boundaries and replay qualification`
8. After Tasks 17–20: `feat(release): qualify populated generational clients in one image`
9. After Tasks 21–23: `test(v3): qualify end-to-end generational civilization benchmarks`

## Blocking Conditions and Non-Goals

No unresolved architecture question blocks starting Task 1. Actual trajectories, positive visual marker coverage, performance and external environment availability must be measured, not invented. The plan commits the procedure and the failure status, not future success.

- Full qualification requires disposable PostgreSQL/pgvector, the pinned Godot suite, a built release image, real browser driver and explicit time/disk/RAM budgets. Missing prerequisites leave the corresponding gate unexecuted and block a full certification claim.
- If valid current policies cannot produce a required controlled positive visual trajectory within the fixed budget, report that acceptance blocker. Do not seed a ledger, create an objective institution, search for a favorable seed or weaken null-capable research checks. A new behavior policy beyond the explicit learner profile requires separate scoped planning.
- No new SQL migration, world command/event, observer semantic type, API version, metric family, capability slot, global truth/technique/culture/office registry or distributed infrastructure.
- No durable subjective resume, adaptive/nested forks, recorded/live LLM fork continuation, forced emergence, automatic debt/inheritance law or deletion of historical provenance.
- Leave preexisting untracked `clients/godot-observer/scripts/net/research_focus.gd.uid`, `clients/godot-observer/scripts/ui/research_focus_panel.gd.uid` and `clients/godot-observer/tests/test_research_focus.gd.uid` untouched.
- Active V3-43 work is treated as completed contextual evidence only where documented: its index reports Tasks 1–21 complete with a browser gate unexecuted. Do not preload its phase history or infer browser certification.

## Approved Refinements

Approved during `$aif-improve` on 2026-10-27. Original Request bytes, all 23 task IDs, task states, phase links and commit groups are preserved; no new task or dependency is introduced.

1. Tasks 2, 13, 22: explicitly disable competing generation/extinction/threshold/criteria stops, synchronize grouped horizons/windows, and require full H coverage rather than any nonfailure result.
2. Tasks 2–3, 12, 22: verify actual founder/newborn mode vectors, scope founder-only effects to founder lifetime windows, and label changed initializer packs as composite treatments.
3. Tasks 4, 13, 15: define a terminal-safe detached research projection and isolated observation lifecycle; preserve fork/finalization guards and science under probe failure.
4. Task 16: exercise real archival RECORD/REPLAY composition through normal provider/store construction with truthful reproducibility modes, positive usage receipts and the existing untracked-custom-provider rejection.
5. Tasks 5, 19–20, 22: define revision plus clean/digest source arguments, verified image labels and no-Git producer forwarding; update commands and failure tests without inventing source cleanliness.
6. Tasks 19–21: refactor release Research UI wiring tests to the authenticated image-owned stack, produce the real V2 matrix summary and eliminate the host frontend-build prerequisite.

## Definition of Done

- All 23 indexed tasks have verified completion evidence; only this index holds task progress checkboxes.
- All 30 requested scenarios have individual executable recipes, mechanism coverage, source-preserving measurements and honest null/unavailable states.
- All thirteen generational invariants and seven replay requirements have explicit checks with applicable source kinds, including nonvacuous independent recorded cognition replay.
- Required V1/V2/default/integration/Compose/Godot/Research UI regressions actually execute and pass; no required skipped lane is silently certified.
- Both release clients inspect source-backed populated multi-generation history, the eight visual markers and nine Research UI domains, without mutating science or requiring host export/build tools.
- Five predeclared numeric-seed research blocks and deterministic twins have reproducible retained artifacts and qualified inference; no emergence/effect direction is required.
- Long-horizon attempts preserve provenance and measured/incomplete distinctions; supported claims stop at verified workloads.
- Documentation and final verification match actual source/release artifacts. Deferred flags and roadmap ownership remain explicit and unchanged.
