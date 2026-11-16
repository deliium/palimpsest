<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: Scientific Hypotheses

Mode: ultra
Branch: main
Created: 2026-11-16

## Original Request

v4-27 scientific hypotheses

Naming requirement:

Use `v4-27-scientific-hypotheses`.

Extend subjective causal world models into explicitly testable hypotheses.

Represent:

claim  
conditions  
predicted result  
confidence  
supporting observations  
contradictions  
creator/source  
historical revisions

Agents may intentionally formulate tests.

Do not expose objective rules.

Hypotheses can be wrong.

## Settings

- Testing: yes; full strategy. Unit, architecture, determinism, properties,
  integration, Compose config/browser, Godot regression (existing suite only),
  Research UI, benchmark regression, and static gates, with coverage enabled
  for Python lanes.
- Logging: verbose, metadata-only. Bounded DEBUG hypothesis/test/revision counts
  and detection milestones; INFO ownership, analysis composition, and
  publication milestones; WARN truncation, malformed frames, cap hits, unlinked
  trials, and collection failures; ERROR safe codes. `PALIMPSEST_LOG_LEVEL`
  controls verbosity. Never log claims, conditions, predicted outcomes, operand
  ids, evidence ids, owner tokens, cursor keys, digests, credentials, DSNs,
  memories, embeddings, or payload surrogates.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 19.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints are suggestions, not authorization to
  commit during planning or implementation unless the user explicitly asks.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-27-scientific-hypotheses`; this plan is the ultra
  bundle `.ai-factory/plans/v4-27-scientific-hypotheses/`. Python tokens use
  `scientific_hypotheses` / `scientific-hypotheses-*`; the feature name is
  "scientific hypotheses".
- Research source: `.ai-factory/RESEARCH.md` and `.ai-factory/research/` do not
  exist; no external research conclusions are invented.
- Execution: plan only in this invocation. No implementation, commit, roadmap
  edit, or branch creation occurs while planning.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"
Rationale: V4-27 owns the already-declared `science` V4 context on the accepted
`runner-config-v56` seam and deepens the owned `predictive_world_model` and
bounded-experimentation mechanisms with an owner-scoped testable-hypothesis
ledger; it adds no V4 context, capability slot, runner schema, command, event,
write pair, API version, or migration, and it does not close M8 or edit other
milestones.

## Requirements Reconciliation

Authority: the Original Request defines scope. `.ai-factory/ARCHITECTURE.md`
("Key Principles", "Versioned Extension Contract", V4-01, V4-03, V4-06, V4-19,
V4-24, V4-25, V4-26 seams) and `.ai-factory/RULES.md` constrain every edit.
`.ai-factory/DESCRIPTION.md` describes the implemented state;
`.ai-factory/ROADMAP.md` is stale for V4-23 through V4-26 and stays owned by
`$aif-roadmap`. Concrete contracts come from the source paths below. No
requirement source is edited to create this plan.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-27 owns the already-declared `science` V4 capability flag: authority `owner_scoped`, owning packages `agents.cognition` + `simulation`, seam `v4_capability_flags.science`, `uses_existing_events=True`, prerequisite `formal_rules`; contexts stay 17, flags 12, owned 8 -> 9, unowned 4 -> 3, map stays `v4-context-map-v5` | Original Request "Extend subjective causal world models into explicitly testable hypotheses"; `src/simulation/v4_architecture.py:74,235-250,388-400`; `src/simulation/versioning.py:111` | Task 1/18/21 |
| `science` is already reuse-only in `V4_EVENT_REUSING_CONTEXTS`; owning it needs no reserved or deepening write pair, no migration stage, and no Alembic change | `src/simulation/versioning.py:102-178`; `src/simulation/migration_plan.py:24-131` | Task 1/18 |
| No `runner-config-v57`, runner root field, per-agent cognition key, capability slot, command, event, observer semantic type, write pair, `/v2` route, or SQL migration is added; `runner-config-v56` remains the accepted seam and the command count stays 43 | `src/simulation/runner_models.py:307-339,1143,8232-8244`; `src/simulation/compatibility.py:155-166,778-801`; `src/simulation/runner_serialization.py:1811-1816,4825-4842` | Task 1/18/21 |
| Science activation is exactly v56 + `science` + `predictive_world_model` + `bounded_experimentation`; science without either prerequisite fails closed, and `science=False` is byte-identical legacy behavior | `src/simulation/runner_models.py:4752-4851,8232-8276`; `src/simulation/runner.py:2456-2528` | Task 1/15/17 |
| The feature extends the existing owner-scoped experiment ledger and causal world model rather than creating a parallel store; the ledger already carries claim components, predicted outcome, support/counter, evidence ids, and trials, and it is exported through the owner checkpoint with a public if-present accessor | `src/agents/cognition/experimentation.py:99-205,275-356,499-613`; `src/agents/cognition/world_model.py:205-336`; `src/simulation/agent_runtime.py:4007-4038` | Task 3/4/9/16 |
| The test action already exists as the closed `Experiment` command and `ExperimentResolved` event; V4-27 must not add a second test command or widen replay-v27/codec `v25` | `src/world/actions.py:650-680,957-1003`; `src/world/experimentation.py:8-47`; `src/world/_experiment_apply.py:52-84`; `src/world/events.py:2225-2265` | Task 5/7/16 |
| `ExperimentResolved` carries objective rule payload (`delta`, `product_id`, `harm_band`, health fields); V4-27 copies only event id, tick, operator, outcome class, and discovery mode. It must not add `hypothesis_id` to the event, which would silently widen replay-v27 | `src/world/events.py:2225-2265`; `src/world/_experiment_apply.py:52-84`; `.ai-factory/ARCHITECTURE.md` requirement 1 | Task 7/9/17/20 |
| Objective laws are world-only configuration (`BoundedExperimentationSpec.laws`, `world._experiment_laws`); cognition receives only caps via `cognition_binding_from_spec`, and the new hypothesis/analysis modules must never read law rows | `src/agents/cognition/experimentation.py:76-95`; `src/world/_experiment_apply.py:1`; `src/simulation/runner_models.py:4752-4795` | Task 2/5/9/17 |
| The requested representation maps to explicit fields: claim (`HypothesisClaim`), conditions (ten closed observation slots), predicted result (`ExperimentOutcomeClass`), confidence (integer milli support ratio), supporting observations (`evidence_event_ids`), contradictions (`counter_evidence_event_ids`), creator/source (`HypothesisSourceKind` + token), and append-only revisions (`HypothesisRevision`) with formulation and revision ticks | Original Request representation list; `src/agents/cognition/experimentation.py:99-205`; `src/agents/cognition/world_model.py:238-336` | Task 2/3/4/20 |
| Intentional tests replace only a default `Wait` and only when conditions hold and the per-tick trial cap allows; a meaningful command is never overridden. This is the V4-20 `Wait` replacement precedent without a new command | Original Request "Agents may intentionally formulate tests"; `src/agents/cognition/loop.py:7327-7330`; `src/agents/cognition/experimentation.py:499-613` | Task 5/16/17 |
| `hyp_v1` travels inside existing `Talk`/`Tell`; attachment happens at the loop result boundary where the owner ledger is in scope, at most one frame for a recently tested claim, and adoption is testimony, not evidence, starting with zero support/zero contradictions and a receiver-observed delivery event token. No event or observer semantic type is added | `.ai-factory/ARCHITECTURE.md` "Memory, testimony, and subjective concepts"; `src/agents/cognition/loop.py:7327-7330`; `src/agents/cognition/formal_rule_communication.py:344-548`; `src/agents/cognition/evidence_testimony_communication.py:393-574` | Task 6/17 |
| Hypotheses are owner-relative beliefs with `provisional`, `supported`, `contradicted`, `inconclusive`, `superseded`, and `retired` statuses. A wrong prediction increments contradiction mass and is retained; no truth, verified, proven, accuracy, calibration, or composite scientific score exists | Original Request "Hypotheses can be wrong"; `src/agents/cognition/world_model.py:205-268`; `src/agents/cognition/experimentation.py:275-356` | Task 2/4/17/20 |
| Detached analysis keeps objective `ExperimentResolved` evidence, owner hypothesis/test/revision rows, and analytical summaries in three separated layers with a hard leakage guard; owner ids, `counterpart` condition values, and objective rule payload never reach analytical rows or the snapshot | `.ai-factory/ARCHITECTURE.md` Key Principle 1; `src/analysis/economic_cascades_contract.py:154-298`; `src/analysis/social_mobility_contract.py:249-272` | Task 2/7/9/17 |
| Six metric families append 244 -> **250**: structure, evidence, test activity, revisions, provenance, and prediction outcomes. The first 244 ids, order, versions, and value keys stay unchanged | `src/analysis/specifications.py:53,318-325,9199-9251,10682-10689`; `src/analysis/metric_service.py:449,2831-2883` | Task 8/18/20/21 |
| The artifact is a sibling `scientific-hypotheses-snapshot-v1` with store `scientific-hypotheses-store-v1`, two dual-gated settings, window-bound cursors, and seven GET-only routes failing closed with `scientific_hypotheses_disabled`; it is not a runner/result/replay/SQL schema | `src/simulation/economic_cascades_models.py:27-380`; `src/simulation/economic_cascades_ports.py:18-84`; `src/persistence/economic_cascades_filesystem.py:115-244`; `src/infrastructure/settings.py:276-279,530-539,987-999` | Task 10-13/21 |
| Publication is programmatic and post-completion; no CLI producer and no runner flag is added | `src/experiments/economic_cascades_publication.py:73-249`; V4-20 through V4-26 have no CLI producer | Task 12/21 |
| No Godot overlay is added: hypotheses are owner-scoped beliefs and detached analysis, not a presentation fact; the presentation client is unchanged and its existing suite is the regression gate | Original Request "Do not expose objective rules"; `.ai-factory/ARCHITECTURE.md` V3-40 through V3-42 seam | Task 14/17/21 |
| Off-gate experiment `scientific_hypotheses@1` composes existing flags and the bounded-experimentation spec in three arms and never enters the V1 A-E gate; the baseline arm has `science=False` and is provably inert | `src/experiments/catalog.py:2800-2841,4510-4565,5776-5792`; `src/experiments/economic_cascades_scenario.py:46,92-172`; `tests/unit/test_v1_regression_gate.py:47-53,217-224` | Task 15/21 |
| Documentation covers `docs/scientific-hypotheses.md`, README, ARCHITECTURE, DESCRIPTION, `docs/architecture.md`, `docs/configuration.md`, `docs/analysis-metrics.md`, `docs/research-api.md`, `docs/v4-architecture.md`, `docs/research-ui.md`, `docs/v4-versioning.md`, `docs/development.md`, `docs/cognition-runtime.md`, `docs/experiments.md`, and `AGENTS.md`; roadmap registration stays with `$aif-roadmap` | `.ai-factory/ARCHITECTURE.md` requirement 7; `.ai-factory/ROADMAP.md`; `docs/economic-cascades.md` | Task 19/20/21 |
| Known drift to correct: `docs/v4-architecture.md` still calls science deferred, and several current-state docs still say 14/15/16 contexts, 8 owned / 4 unowned, 244 or 136/140 families, or old replay/codec surfaces; V4-27 normalizes current-state wording to 17 contexts, 9 owned / 3 unowned, 250 families, and replay-v27/codec `v25` while leaving historical landing notes intact | `docs/v4-architecture.md:13-16,68-79,174-179,249,317-338,477,504,529`; `docs/configuration.md:307-314`; `docs/development.md:311,323`; `docs/analysis-metrics.md:41,774`; `docs/v4-versioning.md:18-26`; `docs/architecture.md:600,714,733,777,803` | Task 18/19/20 |

### Supported combinations and coverage transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| `science=False` | Untouched legacy experiment ledger | No test replacement, no science analysis, no metric input, no snapshot field | Task 1/5/15 |
| `science=True` without `bounded_experimentation` | Config rejected | ValueError `science_requires_bounded_experimentation` | Task 1 |
| `science=True` without `predictive_world_model` | Config rejected | ValueError `science_requires_predictive_world_model` | Task 1 |
| `science=True` with both prerequisites | Owner ledger enriched | Conditions/confidence/source/revisions active; no schema change | Task 1/3 |
| Hypothesis formulated | Provisional row | One `formulated` revision; no command | Task 3/4 |
| Conditions hold and selected command is `Wait` | One `Experiment` command | `hypothesis_id` set; one `test_formulated` revision; trial cap respected | Task 5 |
| Conditions hold but selected command is not `Wait` | Meaningful command retained | No test replacement; no revision | Task 5/17 |
| Conditions mismatch | Hypothesis retained | No command; reason `scientific_hypothesis_untestable` | Task 5 |
| Trial cap reached | No command | Reason `experiment_trial_cap`; no revision | Task 5 |
| Observed outcome equals prediction | Support +1 | Evidence appended; confidence/status recomputed; `support_added` revision | Task 4 |
| Observed outcome differs, including `unexpected` | Contradiction +1 | Counter evidence retained; `contradiction_added` revision; hypothesis can be `contradicted` | Task 4/16 |
| Duplicate trial event id | No change | Idempotent no-op | Task 4 |
| Communicated `hyp_v1` claim | Provisional adopted row | Source `communicated`; zero support/contradictions; no evidence copied | Task 6 |
| Same claim received twice | One row | Idempotent adoption | Task 6 |
| Revision cap exceeded | Newest 32 revisions | Indexes stay monotonic; WARN `scientific_hypotheses_evidence_capped` / truncated history | Task 3/4 |
| Hypothesis cap exceeded | Deterministic eviction | Lowest confidence, then oldest, then id | Task 3 |
| No exported ledgers or no science | No analysis | No `scientific_hypotheses_*` metric input and no snapshot field | Task 9/15 |
| Science ledgers, no trials | Structure/evidence only | Outcome/test families report `insufficient_samples` | Task 7/8 |
| Fewer than 3 hypotheses or trials | Counts retained | `availability=insufficient_samples`; no availability claim | Task 7/8 |
| `ExperimentResolved` with delta/product/harm | Safe fields only | Rule payload is never copied into facts, rows, snapshot, or routes | Task 7/9/17 |
| Cap exceeded for events, hypotheses, conditions, revisions, trials, summaries, or notices | Deterministic prefix | `coverage="partial"` plus one bounded notice per family | Task 7/17 |
| Snapshot dual gate unset | No reader | 503 `scientific_hypotheses_disabled` on all seven routes | Task 11/13 |
| Corrupt snapshot payload | No data | 500 `scientific_hypotheses_store_corrupt` | Task 10/13 |
| Paged route with `window_index` | Filter-bound cursor | Only matching rows; cursor for another window rejected 400 | Task 10/13 |
| Publication disabled by the caller | No artifact | Nothing written; scientific status unchanged | Task 12 |
| Env-gated lane missing prerequisite | No green certification | `unexecuted` plus prerequisite | Task 21 |

No blocking open questions: every material decision is fixed below.

## Architecture and Decisions

1. **Own the declared context, add no context.** `science` is already the ninth
   flagged V4 context. V4-27 claims it; contexts stay 17, flags 12, owned 9,
   unowned 3, map `v4-context-map-v5`.
2. **No runner schema bump.** Science activation uses the V4 flag plus two
   existing prerequisites: the owned V2 `predictive_world_model` flag and the
   existing `BoundedExperimentationSpec`. `runner-config-v56` remains the
   accepted-only seam; there is no v57 and no per-agent `hypothesis_mode`.
3. **Deepen the existing ledger, do not fork a store.** `ExperimentHypothesis`
   becomes the explicit testable hypothesis; `CausalHypothesis` remains the
   predictive belief. The optional `causal_hypothesis_id` records the lineage
   from a causal belief to a testable claim, and the ledger is exported through
   the owner checkpoint with a public if-present accessor.
4. **No new command or event.** Intentional tests use the existing `Experiment`
   command and `ExperimentResolved` event. Command count stays 43; replay stays
   v27/codec `v25`.
5. **Objective rules stay world-only.** `BoundedExperimentationSpec.laws` and
   `world._experiment_laws` are never read by cognition, analysis, the bridge,
   snapshot, routes, or UI. The analysis copies only five safe event fields.
6. **Intentional tests are conservative.** Only a default `Wait` is replaced,
   only when conditions hold, and only within the per-tick trial cap. A
   meaningful action is never overridden.
7. **Conditions are observations, not rules.** The ten closed slots are
   location, day phase, weather, held item kind, counterpart, season,
   temperature band, hazard, action, and concept. They are checked against the
   owner's current observation; an absent attribute is unsatisfied, never
   guessed.
8. **Confidence is a support ratio.** Integer milli with a fixed prior; it is
   not a probability, calibration, accuracy, or score.
9. **Hypotheses can be wrong.** Statuses are owner-relative; contradictions are
   appended, retained, and visible. No truth, verified, proven, or proof field
   exists.
10. **Creator/source is provenance, not trust.** Self-formulated, observed,
    remembered, communicated, recorded, and unknown sources are descriptive; a
    communicated claim starts with zero evidence, and its source token is the
    receiver-observed delivery event, never the sender's agent id.
11. **Revisions are append-only.** Each formulation, revision, evidence update,
    source adoption, test, supersession, and retirement appends one bounded
    revision with a monotonic index.
12. **Three layers stay separate.** Objective `ExperimentResolved` evidence,
    owner hypothesis/test/revision rows, and analytical summaries have a hard
    leakage guard; owner ids, `counterpart` condition values, and rule payload
    never reach analytical rows or the snapshot.
13. **Bounded everything.** Per-hypothesis conditions/revisions/evidence and
    per-analysis owners/hypotheses/revisions/trials/summaries/notices have
    independent caps with deterministic prefixes and `partial` coverage.
14. **Longitudinal windows.** `window_ticks=32`, `max_windows=512`; rows carry
    window index and tick; the summary reports the latest window and count.
15. **Activation is evidence-driven.** Analysis requires the `science` flag,
    the bounded-experimentation prerequisite, exported ledgers, and committed
    events; otherwise no metric input and no snapshot field, so default V1/V2
    bundles are unchanged.
16. **Read-only surfaces.** `scientific-hypotheses-snapshot-v1` is canonical,
    digest-addressed, and wall-clock-free; `scientific-hypotheses-store-v1` is
    atomic, quota-bounded, idempotent, and corruption-safe; seven GET-only
    dual-gated routes serve it; publication is programmatic after completion.
17. **No presentation physics.** No Godot overlay and no client write path; the
    Research UI panel is read-only.
18. **Catalog discipline.** Six families append exactly at positions 244-249;
    every active pin and current-state doc is swept from 244 to 250 in one
    change while historical landing notes stay intact.

### Locked scientific-hypotheses summary

| Surface | Locked behavior |
| --- | --- |
| Policy | `scientific-hypotheses.v1` (cognition, analysis, and snapshot share the token) |
| V4 ownership | `science` owned; 17 contexts / 12 flags / 9 owned / 3 unowned; map `v4-context-map-v5` |
| Runner schema | `runner-config-v56` only; no v57, no new root or per-agent key |
| Activation | v56 + `science` + `predictive_world_model` + `bounded_experimentation`; otherwise inert or fail closed |
| Owner ledger | `ExperimentLedger` with claim, conditions, predicted result, confidence milli, support/contradiction evidence, source, status, revisions, and formulation/revision ticks |
| Causal link | Optional `causal_hypothesis_id`; no causal-model mutation from trials |
| Conditions | `location`, `day_phase`, `weather`, `held_item_kind`, `counterpart`, `season`, `temperature_band`, `hazard`, `action`, `concept` |
| Predicted result | `ExperimentOutcomeClass`: `success`, `partial_success`, `failure`, `harm`, `unexpected`; strict equality; `unexpected` always contradicts |
| Confidence | Integer milli `(support + 1) / (support + counter + 2)`; not a probability |
| Status | `provisional`, `supported`, `contradicted`, `inconclusive`, `superseded`, `retired` |
| Source | `self_formulated`, `observed`, `remembered`, `communicated`, `recorded`, `unknown` |
| Revisions | Append-only, monotonic index and tick, max 32 per hypothesis; reasons include `formulated`, `prediction_revised`, `condition_revised`, `support_added`, `contradiction_added`, `source_adopted`, `test_formulated`, `superseded`, `retired` |
| Intentional test | Replace only `Wait`; one `Experiment`; conditions must hold; per-tick trial cap |
| Communication | `hyp_v1` inside `Talk`/`Tell`; adoption is provisional and evidence-free |
| Rules guard | No law/rule/probability/delta/product/harm key; no `world._experiment_laws` import; five-field event allowlist |
| Window | 32 ticks; index `tick // 32`; at most 512 windows |
| Caps | 32 hypotheses/owner, 8 conditions, 32 revisions, 64 evidence refs each side; analysis 64 owners, 4,096 hypotheses, 8,192 conditions/revisions, 4,096 trials, 1,024 summaries, 8 notices |
| Snapshot | `scientific-hypotheses-snapshot-v1`; store `scientific-hypotheses-store-v1`; 16 publications / 8 MiB; no wall-clock or owner field |
| Routes | 7 GET-only under `SUBJECTIVE_DEBUG`; default limit 100; max 500; `window_index` <= 511; `scientific_hypotheses_disabled` when unset |
| Catalog | 244 -> 250 families; first 244 unchanged |
| Clients | Research UI panel; no new Godot overlay |
| Experiment | `scientific_hypotheses@1`, off the V1 gate, three arms; the communicated arm proves one `hyp_v1` adoption or is `unexecuted` |
| Pins | 43 commands; 73 observer semantics; replay-v27/codec `v25`; Alembic `0017`; `/v1`; `observer-protocol-v1` |

## Phase Index

1. [Phase 1: Science Ownership, Contract, and Owner Ledger](phase-01-science-contract-ledger.md) — Tasks 1-4
2. [Phase 2: Intentional Tests, Communication, Analysis, and Metrics](phase-02-tests-communication-metrics.md) — Tasks 5-8
3. [Phase 3: Ledger Export, Snapshot, Store, and Publication](phase-03-artifact-publication.md) — Tasks 9-12
4. [Phase 4: Read Surfaces](phase-04-read-surfaces.md) — Tasks 13-14
5. [Phase 5: Experiment and Certification Paths](phase-05-experiment-certification.md) — Tasks 15-17
6. [Phase 6: Invariants, Documentation, and Certification](phase-06-invariants-docs.md) — Tasks 18-21

## Cross-Phase Dependencies

- Task 2 depends on Task 1 for the owned `science` activation and policy names.
- Task 3 depends on Task 2 for condition slots and closed status/source tokens.
- Task 4 depends on Task 3 for the enriched ledger and revision types.
- Task 5 depends on Tasks 1, 3, and 4 for activation, conditions, and lifecycle.
- Task 6 depends on Task 3 for claims and Task 4 for adoption revisions.
- Task 7 depends on Task 2 for detached facts/rows and Task 4 for lifecycle
  evidence.
- Task 8 depends on Task 7 for `ScientificHypothesesAnalysis`.
- Task 9 depends on Tasks 2, 4, and 7 for fact mapping and analysis.
- Task 10 depends on Task 7 for row availability and snapshot fields.
- Task 11 depends on Task 10 for encode/decode.
- Task 12 depends on Tasks 7, 9, 10, and 11 for analyze -> compose -> store.
- Task 13 depends on Tasks 10 and 11 for paging, cursors, and the reader.
- Task 14 depends on Task 13 for the route contract.
- Task 15 depends on Tasks 1, 9, and 12 for flag ownership, collector, and
  publication.
- Task 16 depends on Tasks 5, 9, 12, and 13 for the real path; it does not
  depend on experiment registration because it builds its own v56 run.
- Task 17 depends on Tasks 3-16 for determinism, bounds, and leakage fixtures.
- Task 18 depends on Tasks 1-17 for the final pin sweep.
- Task 19 depends on Task 18 for the current-state docs count sweep.
- Task 20 depends on Task 19 for the positive and negative parity assertions.
- Task 21 depends on Tasks 15-20.

## Tasks

### Phase 1: Science Ownership, Contract, and Owner Ledger
- [x] Task 1: Own the `science` V4 capability flag and lock activation ([details](phase-01-science-contract-ledger.md#task-1-own-the-science-v4-capability-flag-and-lock-activation))
- [x] Task 2: Lock the `scientific-hypotheses.v1` contract, policy, and detached row DTOs ([details](phase-01-science-contract-ledger.md#task-2-lock-the-scientific-hypothesesv1-contract-policy-and-detached-row-dtos))
- [x] Task 3: Extend the owner experiment ledger with explicit claim, conditions, source, and revisions ([details](phase-01-science-contract-ledger.md#task-3-extend-the-owner-experiment-ledger-with-explicit-claim-conditions-source-and-revisions))
- [x] Task 4: Implement deterministic support, contradiction, confidence, and revision lifecycle ([details](phase-01-science-contract-ledger.md#task-4-implement-deterministic-support-contradiction-confidence-and-revision-lifecycle))

### Phase 2: Intentional Tests, Communication, Analysis, and Metrics
- [x] Task 5: Wire intentional scientific tests from `Wait` to one `Experiment` ([details](phase-02-tests-communication-metrics.md#task-5-wire-intentional-scientific-tests-from-wait-to-one-experiment)) (depends on 1, 3, 4)
- [x] Task 6: Add `hyp_v1` claim communication and communicated adoption ([details](phase-02-tests-communication-metrics.md#task-6-add-hyp_v1-claim-communication-and-communicated-adoption)) (depends on 3, 4)
- [x] Task 7: Compose the bounded `ScientificHypothesesAnalysis` harvest ([details](phase-02-tests-communication-metrics.md#task-7-compose-the-bounded-scientifichypothesesanalysis-harvest)) (depends on 2, 4)
- [x] Task 8: Append six metric families (244 -> 250) and wire the service ([details](phase-02-tests-communication-metrics.md#task-8-append-six-metric-families-244---250-and-wire-the-service)) (depends on 7)

### Phase 3: Ledger Export, Snapshot, Store, and Publication
- [x] Task 9: Export experiment ledgers and wire completed-run inputs ([details](phase-03-artifact-publication.md#task-9-export-experiment-ledgers-and-wire-completed-run-inputs)) (depends on 2, 4, 7)
- [x] Task 10: Add snapshot models, codec, paging, and ports ([details](phase-03-artifact-publication.md#task-10-add-snapshot-models-codec-paging-and-ports)) (depends on 7)
- [x] Task 11: Add the atomic store and dual-gated settings ([details](phase-03-artifact-publication.md#task-11-add-the-atomic-store-and-dual-gated-settings)) (depends on 10)
- [x] Task 12: Compose and publish completed-run snapshots ([details](phase-03-artifact-publication.md#task-12-compose-and-publish-completed-run-snapshots)) (depends on 7, 9, 10, 11)

### Phase 4: Read Surfaces
- [x] Task 13: Add seven GET-only dual-gated routes ([details](phase-04-read-surfaces.md#task-13-add-seven-get-only-dual-gated-routes)) (depends on 10, 11)
- [x] Task 14: Add the Research UI client and panel ([details](phase-04-read-surfaces.md#task-14-add-the-research-ui-client-and-panel)) (depends on 13)

### Phase 5: Experiment and Certification Paths
- [x] Task 15: Register off-gate `scientific_hypotheses@1` ([details](phase-05-experiment-certification.md#task-15-register-off-gate-scientific_hypotheses1)) (depends on 1, 9, 12)
- [x] Task 16: Add in-process end-to-end coverage ([details](phase-05-experiment-certification.md#task-16-add-in-process-end-to-end-coverage)) (depends on 5, 9, 12, 13)
- [x] Task 17: Add determinism, property bounds, and no-rule leakage coverage ([details](phase-05-experiment-certification.md#task-17-add-determinism-property-bounds-and-no-rule-leakage-coverage)) (depends on 3-16)

### Phase 6: Invariants, Documentation, and Certification
- [x] Task 18: Sweep science ownership, catalog, and documentation pins ([details](phase-06-invariants-docs.md#task-18-sweep-science-ownership-catalog-and-documentation-pins)) (depends on 1-17)
- [x] Task 19: Documentation via `$aif-docs` ([details](phase-06-invariants-docs.md#task-19-documentation-via-aif-docs)) (depends on 18)
- [x] Task 20: Add documentation pin and negative parity checks ([details](phase-06-invariants-docs.md#task-20-add-documentation-pin-and-negative-parity-checks)) (depends on 19)
- [x] Task 21: Required-gate verification certification ([details](phase-06-invariants-docs.md#task-21-required-gate-verification-certification)) (depends on 16-20)

## Commit Plan

- **Commit 1** (after tasks 1-4): `feat(cognition): own science and add testable hypothesis ledger`
- **Commit 2** (after tasks 5-8): `feat(analysis): compose scientific hypothesis evidence and metrics`
- **Commit 3** (after tasks 9-14): `feat(simulation): publish scientific hypothesis snapshots and read surfaces`
- **Commit 4** (after tasks 15-17): `test: certify scientific hypothesis experiment and end-to-end paths`
- **Commit 5** (after tasks 18-21): `test,docs: sweep science ownership and catalog pins`

Commit checkpoints are suggestions only. Do not commit during `$aif-implement`
unless the user explicitly authorizes commits.

## Definition of Done

- V4-27 owns exactly the already-declared `science` V4 capability flag; counts
  are 17 contexts / 12 flags / 9 owned / 3 unowned; the map stays
  `v4-context-map-v5`; no new context, capability slot, `runner-config-v57`,
  runner root field, per-agent key, command, event, observer semantic type,
  write pair, `/v2` route, or migration is added.
- Science activates only with v56, `science`, `predictive_world_model`, and
  `bounded_experimentation`; every missing prerequisite fails closed and
  `science=False` is a byte-identical passthrough.
- The owner ledger explicitly represents claim, conditions, predicted result,
  confidence milli, supporting observations, contradictions, creator/source,
  and append-only historical revisions.
- Objective rules, law rows, probabilities, deltas, product ids, and harm bands
  are never read by cognition, analysis, the bridge, snapshot, routes, or UI;
  `ExperimentResolved` contributes only five safe fields.
- Intentional tests use the existing `Experiment` command, replace only a
  default `Wait`, respect conditions and the per-tick trial cap, and never
  override a meaningful command.
- `hyp_v1` communication is testimony only; adoption creates a provisional,
  zero-evidence row and never copies evidence.
- Hypotheses can be wrong: contradictions are retained, `contradicted` and
  `inconclusive` are first-class, and no truth, verified, proven, accuracy,
  calibration, or composite scientific score exists.
- Objective evidence, owner hypothesis/test/revision rows, and analytical
  summaries are separate layers with a hard leakage guard; owner ids never
  reach analytical rows or the snapshot.
- Six metric families append exactly at positions 244-249; the first 244 ids,
  order, versions, and value keys are unchanged; every active pin and
  current-state doc is swept to 250.
- Analysis activates only with science, exported ledgers, and committed events;
  otherwise no metric input, no snapshot field, and no off-path change.
- `scientific-hypotheses-snapshot-v1` round-trips canonically with no wall-clock
  or owner field; `scientific-hypotheses-store-v1` is atomic, quota-bounded,
  idempotent, and corruption-safe.
- Seven GET-only dual-gated routes fail closed with
  `scientific_hypotheses_disabled`, default limit 100, max 500, `window_index`
  <= 511; the Research UI panel is read-only; no new Godot overlay exists.
- Publication is programmatic and post-completion; no CLI producer or runner
  flag is added.
- Off-gate `scientific_hypotheses@1` is registered with three arms and is absent
  from the V1 A-E gate; the baseline arm is inert.
- Commands stay 43; observer semantics stay 73; replay-v27/codec `v25` stay the
  maximum; Alembic stays `0017`; `/v1` and `observer-protocol-v1` stay.
- The in-process E2E uses real admission, a real `Experiment` command, real
  events, a real ledger, a real snapshot, a real store, and real API reads, and
  retains at least one contradicted hypothesis.
- Determinism across hash seeds, cap-bound properties, layer separation, and
  no-rule leakage guards pass.
- Docs cover the new page plus README, ARCHITECTURE, DESCRIPTION,
  `docs/architecture.md`, `docs/configuration.md`, `docs/analysis-metrics.md`,
  `docs/research-api.md`, `docs/v4-architecture.md`, `docs/research-ui.md`,
  `docs/v4-versioning.md`, `docs/development.md`, `docs/cognition-runtime.md`,
  `docs/experiments.md`, and `AGENTS.md`, with positive and negative parity
  checks.
- Required gates are certified or explicitly `unexecuted`; the roadmap remains
  owned by `$aif-roadmap`, which must register V4-23 through V4-27 later.

## Verification Receipt

Filled by Task 21. No lane is green until its command and result are recorded
here.

| Lane | Command | Result | Prerequisite / note |
| --- | --- | --- | --- |
| Unit + architecture correctness | `uv run pytest tests/unit tests/architecture -q` | green: 12,178 passed, 1 skipped (12:52) |  |
| Focused scientific-hypothesis suites | `uv run pytest tests/unit/test_scientific_hypotheses_*.py tests/architecture/test_scientific_hypotheses_*.py tests/integration/test_scientific_hypotheses_store_api.py -q` | green: focused 189 passed; integration file 1 passed with `-m integration` | integration lane runs separately with `-m integration` |
| Python coverage (focused) | `uv run pytest tests/unit/test_scientific_hypotheses_*.py tests/architecture/test_scientific_hypotheses_*.py -q --cov=src --cov-report=term` | green: 189 passed; lane TOTAL 25% | lane-scoped coverage only; full `src` denominator is dominated by unrelated modules |
| Python coverage (full lane) | `uv run pytest tests/unit tests/architecture -q --cov=src --cov-report=term` | unexecuted: timed out at the 2400 s harness limit | full suite without coverage is green; rerun the coverage lane with a longer limit |
| Static: Ruff | `uv run ruff check src tests` | green: all checks passed |  |
| Static: mypy | `uv run mypy src tests` | green: no issues in 2,860 files |  |
| Static: import boundaries | `uv run lint-imports` | green: 25 kept, 0 broken |  |
| Integration (non-scale) | `uv run pytest tests/integration -m "not scale" -q` | green: 63 passed, 60 skipped, 5 deselected | PostgreSQL-free lanes |
| Scientific-hypothesis store/API integration | `uv run pytest tests/integration/test_scientific_hypotheses_store_api.py -q -m integration` | green: 1 passed |  |
| Compose config | `docker compose config` | green: exit 0 |  |
| Research UI tests | `cd clients/research-ui && ./node_modules/.bin/vitest run` | green: 329 passed |  |
| Research UI types | `cd clients/research-ui && ./node_modules/.bin/svelte-check --tsconfig ./tsconfig.app.json` | green: 0 errors, 0 warnings |  |
| Godot regression | `GODOT_BIN=~/.cache/palimpsest-godot/Godot_v4.7.2-stable_linux.x86_64 "$GODOT_BIN" --headless --path clients/godot-observer --script res://tests/run_protocol.gd` | green: failed=0 | existing suite only; no client source change |
| Compose/browser acceptance | `PALIMPSEST_API_IMAGE=<matched> PALIMPSEST_V3_ACCEPTANCE_REQUIRED=1 uv run pytest -m compose -q` | unexecuted | requires an attested `PALIMPSEST_API_IMAGE`; none available |
| Benchmark regression (non-scale) | `PALIMPSEST_V4_SCALE_IDS=100000 uv run pytest tests/benchmarks -m "not scale" -q` | green: 1 passed, 20 deselected |  |

`git status` must confirm no `.ai-factory/ROADMAP.md` edit from this plan, no
`alembic/versions/0018*` file, no `clients/godot-observer/` source change, no
`/v2` route, no new V4 capability slot, and no `runner-config-v57`. The science
ownership, cognition ledger, analysis modules, snapshot/store, seven routes,
Research UI panel, six metric families, docs, and off-gate experiment are the
only V4-27 surfaces changed.
