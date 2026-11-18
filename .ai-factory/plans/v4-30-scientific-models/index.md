<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-30 Scientific Models

Mode: ultra
Plan identifier: `v4-30-scientific-models`
Branch: `main` (existing; branch creation disabled)
Created: 2026-11-18
Status: planned; implementation not started

## Original Request

v4-30 predictive models

Naming requirement:

Use `v4-30-scientific-models`.

Allow agents to maintain structured predictive models derived from hypotheses.

Examples:

season forecasting  
resource regeneration  
disease risk  
production outcome

Models must produce predictions before outcomes.

Track:

prediction  
confidence  
actual observed outcome  
calibration  
revision

Enable model comparison through predictive performance.

## Settings

- Testing: yes; focused unit, property, architecture and real-run integration
  coverage, plus default-suite regression checks. Keep coverage enabled.
- Logging: verbose DEBUG metadata-only; never payloads, claims, source conditions,
  distributions, observed outcomes, secrets or payload-surrogate digests.
- Docs: yes; mandatory `$aif-docs` checkpoint during implementation.
- Artifact/UI language: English; preserve technical terms.
- Git: enabled, base `main`, no new branch/worktree, no automatic commit/push.
- Verification: configured `normal`; optional certification lanes reported
  separately rather than implicitly passed.
- Preferences explicitly confirmed by the user. No research source influenced
  this plan; the configured research artifact/bundle directory is absent.
- Implementation entrypoint must be supplied explicitly because this repository
  has multiple plans and branch creation is disabled.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations"

Rationale: Deepen the owned `science` capability with owner-scoped predictive
models, prior forecasts and fallible predictive performance, without adding
world authority, scripted scientific success or a new capability slot.

M8 remains open. V4-30 does not own `epidemics`, `ecological_feedback`,
`disasters`, V3 `institutional_economy`, or V2 `multi_hop_testimony_tracking`.
Any milestone registration/status update belongs to the roadmap owner workflow;
this planning invocation changes only this plan bundle.

## Requirements Reconciliation

Authority: repository `AGENTS.md` and project axioms/rules constrain all work;
the original request defines feature scope within those boundaries; architecture
defines authority/import/version constraints. Code contracts establish existing
accepted inputs and observable evidence. Historical roadmap/landing summaries
are scope/history, not instructions to revert newer accepted contracts.

| Decision / supported behavior | Source path and section | Verification evidence |
| --- | --- | --- |
| Models derive from explicit hypotheses and record prediction, confidence, observed outcome, calibration, revision and comparison | Original Request | Tasks 1–4, 9–11, 15, 20 |
| Models/forecasts are owner-scoped beliefs; world mutation remains engine-only | `.ai-factory/RULES.md` — axioms; `.ai-factory/ARCHITECTURE.md` — authority/dependencies | Tasks 6, 8, 16, 19 |
| Legacy confidence is not probability/calibration; use a distinct predictive contract | `docs/scientific-hypotheses.md` — Confidence/Analysis; `src/agents/cognition/experimentation.py` — `confidence_milli_from_masses`; `src/analysis/scientific_hypotheses_contract.py` — forbidden keys | Tasks 1, 3, 4, 10 |
| Do not fake cross-domain causal/experimental claims | `src/agents/cognition/world_model.py` — `CausalOutcome`; `src/agents/cognition/experimentation.py` — `HypothesisClaim` | Task 2: new typed model hypotheses for observed regularities, explicit existing experimental source adapter |
| Calendar, regeneration policy and production laws are not cognition inputs | `src/world/environment.py` — module contract; `src/world/observations.py` — resource omissions; `.ai-factory/ARCHITECTURE.md` — trust boundaries | Tasks 2, 5, 16, 18 |
| Prior commitment precedes physical outcome, not merely late receipt | Original Request; `src/simulation/engine.py` — tick advancement; `src/simulation/agent_runtime.py` — `finalize_pending` | Tasks 3, 5–8, 18 |
| Production matching cannot rely on nonexistent redacted process/operand fields | `src/world/_perception.py` — `_experiment_public_facts`; owner effective-command finalization in `src/simulation/agent_runtime.py` | Tasks 5–7: separate exact owner action binding and later observed result |
| Resource example predicts observed net quantity direction, not isolated physical regeneration | `src/world/observations.py` — `ObservedResource`, omitted resource regeneration | Tasks 2, 5, 15, 20; explicitly labeled estimand |
| Disease example is explicitly unavailable, not invented biology | `src/simulation/runner_models.py` — unowned epidemics; no disease observable in current world contracts | Tasks 1, 2, 15, 19; no forecast/score for disease |
| Snapshot publication/read stores stay detached and opt-in | `.ai-factory/ARCHITECTURE.md` — analysis-to-artifact boundaries; `src/experiments/replication_publication.py` | Tasks 9–16 |
| Preserve old exact keysets and default/off-path behavior | `.ai-factory/ARCHITECTURE.md` — Versioned Extension Contract; `src/simulation/run_control.py` — v1/v2/v3 requirements | Tasks 7, 19, 22 |

### Supported combinations

| Input / state combination | Validation and persisted state | Output / next transition / invariant | Required test |
| --- | --- | --- | --- |
| `science=False`, any legacy accepted off-path config | Existing validation; predictive state absent | No models, predictive logs, commands or new pending codec | Tasks 6, 19 flags-off canonical parity |
| Science enabled with existing prerequisites, v56 without measurement | Existing science validation; empty/active predictive ledger; pending v4 | Eligible observed/source hypotheses derive models; absence is legal | Tasks 6, 7, 19 |
| Science enabled, v57 measurement spec present | Existing measurement validation; predictive plus existing measurement/replication state | Pending v4, world replay28/v26 remains measurement-selected; no truth from instrument bias | Tasks 7, 17, 19 |
| Science enabled without predictive-world-model/bounded-experimentation prerequisites | Existing configuration rejection | No partial runtime or new fallback mode | Task 19 |
| Environmental season/visible resource source present | Retain owner sample pairs, model hypotheses and revisions | Two-boundary categorical forecasts; no private calendar/rate | Tasks 2, 5, 20 |
| Season/resource absent, occluded or target sample missed | Coverage/pending/unavailable state | No invented observation, no score or denominator contribution | Tasks 5, 18 |
| Owner production hypothesis plus later exact effective `Experiment` | Frozen claim, separate action binding, later observed categorical result | Score only one exact eligible actor occurrence at tick `t+1` | Tasks 5, 6, 18, 20 |
| Production not attempted or command substituted | Original forecast unchanged; no matching binding | `not_attempted`, not failure; denial without result unscored | Tasks 5, 6, 18 |
| Same production claim executed under changed/unknown required conditions | Binding records comparability status | `not_comparable`, no score; never silently pool conditions | Tasks 5, 6, 18 |
| Source absent/temporarily unsatisfied, then restored | Suspend/resume models with explicit revision | No new issuance while suspended; old cases still settle | Tasks 2, 3, 18 |
| Source explicitly retired/superseded | Retire model; replacement gets successor identity/lineage | Never resurrect retired models or cancel their prior forecasts | Tasks 2–5, 18 |
| Disease-risk target requested | Closed target descriptor plus unavailable notice | No disease prediction, probability, inferred illness or calibrated score | Tasks 1, 2, 19 |
| Source/model changes after issuance | New immutable revisions; prior case pins old content | Score frozen forecast, not current prediction | Tasks 3, 4, 7, 18 |
| Same observation/receipt or recovered pending transition repeated | Identity/high-water and integrity validation | Exactly-once case, count and revision | Tasks 5, 7, 8, 18 |
| Model pair has at least three identical observed eligible cases | Paired target/context/unit/horizon cohort | Qualified lower-loss/tie comparison; no global winner | Tasks 4, 10, 20 |
| One model missing, mixed target/cohort, or fewer than three pairs | Explicit exclusions/insufficient state | No substitution, pooled score or confidence in superiority | Tasks 4, 10, 15 |
| Store root and cursor key both absent | Reader disabled; runtime science unaffected | Authorized reads return disabled | Tasks 14, 16 |
| Both read settings valid | Immutable publication reader only | Authorized bounded GET/paging, no build/repair/publication | Tasks 13–16 |
| Exactly one read setting / invalid secret | Fail closed at settings composition | No partially secured surface | Task 14 |
| Publication B appears while cursor A is used | Decode A before reading its signed publication | No latest-publication drift; conflicting selector rejected | Tasks 14–16 |
| Cap reached within a paired case/reference group | Admit/omit complete bundle, surface omissions | Preserve both candidates/reference closure and recompute denominators | Tasks 1, 10, 11, 20 |
| Admitted owner contains actual predictive state | All deny/store lists and real content probes apply | Reject copied/advanced content; pristine frozen ledger counts zero | Tasks 6, 8, 19 |

### Known artifact drift and interpretation

The architecture baseline heading/table still describes V4-28/latest replay27,
while its V4-29 seam and DESCRIPTION specify measurement replay28/v26 and runner
v57. Older hypothesis/configuration narratives say “no v57” for their own landing.
This is historical/current-summary drift, not a reason to reject existing v57.
Executable accepted-set contracts plus the explicit V4-29 seam govern this plan;
Task 22 updates only current summaries after implementation. No change to source
requirements is made during planning.

## Architecture and Decisions

1. **Owned seam:** deepen `science`. No runner v58, new flag/context/mode, root
   sibling, command, world event, observation field, replay pair, domain-envelope
   version, SQL migration or Godot overlay.
2. **New private sidecar:** `ScientificModelLedger` under
   `scientific-models.v1`. A typed `ModelHypothesis` records a fallible structured
   claim derived from owner-observed regularities or an existing experimental
   hypothesis. Existing causal links are provenance, not outcome conversions.
   Do not widen `CausalOutcome`/`HypothesisClaim` to fake unsupported domains.
3. **Concrete domain scope:** season at two future observation boundaries;
   resource direction of net visible quantity change over those boundaries;
   categorical existing production-related `Experiment` result at the next
   execution tick; disease unavailable until a real observable/owned seam exists.
   No numerical yield function, natural-language model code or unrestricted
   executable equation is introduced.
4. **Forecast candidates:** hypothesis-derived baseline weights 2/1 versus
   empirical exact-context counts with Laplace +1 smoothing. Integer
   largest-remainder normalization produces probability milli summing to 1000;
   confidence is chosen-class probability. Legacy support ratios are not inputs
   to either distribution.
5. **Prior commitment:** observation `t` creates a detached immutable candidate;
   ordinary finalization after tick `t` commits it. Target observation is `t+2`;
   eligible production occurrence tick is `t+1`. The immediately next
   observation at `t+1` is intentionally not scored: its physical facts already
   exist by issuance finalization. Track issuance, commitment, physical sample/
   event, target and receipt separately.
6. **Exact production correlation:** append a separate owner effective-command
   binding at tick `t+1`; use only the final command and owner-visible conditions,
   never hidden event details. An outcome arrives through normal observation.
   Changed/unknown required action-time conditions make it noncomparable.
7. **No action-authority expansion:** predictive models do not create or replace
   commands, alter admission, change stop selectors or install truth in memory.
   Owner-local comparison is available in owner state; analytical comparison is
   independently recomputed after completion, never fed back into cognition.
   Sharing predictive models through speech is outside V4-30.
8. **Performance:** multiclass Brier numerator from frozen probabilities, hit
   share, ten-bin calibration and paired loss difference. Qualify target,
   horizon, unit, context, observation channel and retained cohort. At least
   three pairs for descriptive lower-loss/tie status. No significance claim,
   pooled science score, owner ranking, universal winner or scientific truth.
9. **Revision:** append source/parameter revisions; unresolved forecasts pin
   their issuance revisions. New data updates only future distributions.
   Terminal retention has explicit watermarks/eviction counts; published
    performance is not called lifetime accuracy.
    Temporary source loss suspends future issuance; restoration resumes the same
    identity. Retirement is terminal; replacement has successor lineage. Nested
    evidence arrays and aggregated notices are bounded too.
10. **Recovery:** strict `scientific-model-state-v1` and
    `finalization-command-v4`, with predictive digest independent of other
    sidecars. Existing v1/v2/v3 exact contracts and default v1 bytes remain
    unchanged. Checkpoint/fork/retired-owner exports preserve cases and
    deduplication; newborns inherit no content.
    Runtime checkpoint is the single committed model-state source for forks,
    not a duplicate `CognitiveLoopForkState` field. Actual blank-slate content
    probes and all store/deny enumerations enforce fresh admission.
11. **Detached surface:** six new metric families, independent
    `scientific-models-snapshot-v1` / `scientific-models-store-v1`, programmatic
    completed-run publication, eight GET-only dual-gated routes, and a read-only
    Research UI panel. Existing hypothesis “no calibration/score” key restrictions
    remain intact.
    Completed results carry validated owner ledgers to the collector without a
    live runner. Publication caps preserve complete pairs/reference closure and
    recalculate denominators. Cursors select their signed publication before
    reading; filters cannot relabel aggregates as narrower cohorts.
12. **Current pins after implementation:** 262 metric families; 45 commands;
    73 observer semantic types; 17 V4 contexts; 12 flags, nine owned/three
    unowned; `v4-context-map-v6`; default runner/result v4/v2, latest opt-in
    runner v57; world pairs remain feature-selected, measurements28/v26 and
    travel27/v25; Alembic `0017`; `/v1`, `observer-protocol-v1`.

## Scope Boundaries

Included: structured hypothesis-derived models, immutable prior predictions,
predictive confidence, actual owner observations, calibration, append-only
revision, owner-local and detached paired comparison, bounded recoverable state,
read-only publication/API/UI, tests and documentation.

Excluded: epidemic mechanics, hidden rate/calendar/law access, true resource-rate
identification, numeric production functions, automatic best-model action
selection, model speech/adoption, LLM-authored executable code, society-wide
scientific consensus, global knowledge/model registry, scientific truth/quality
scores, new SQL schema, new matrix factors/benchmark registry, automatic CLI
publication, Godot work, capacity claims and unrelated refactors.

## Phase Index

1. [Phase 1: Model contracts](phase-01-model-contracts.md) — Tasks 1–4
2. [Phase 2: Runtime and recovery](phase-02-runtime-and-recovery.md) — Tasks 5–8
3. [Phase 3: Analysis and publication](phase-03-analysis-and-publication.md) — Tasks 9–12
4. [Phase 4: Store, API and UI](phase-04-store-api-and-ui.md) — Tasks 13–16
5. [Phase 5: Experiments and regressions](phase-05-experiments-and-regressions.md) — Tasks 17–20
6. [Phase 6: Documentation and verification](phase-06-documentation-and-verification.md) — Tasks 21–24

## Cross-Phase Dependencies

- Task 2 depends on 1; Task 3 depends on 1 and 2; Task 4 depends on 1 and 3.
- Task 5 depends on 1–4; Task 6 on 5; Task 7 on 1 and 6; Task 8 on 6 and 7.
- Task 9 depends on 8; Task 10 on 4 and 9; Task 11 on 9 and 10; Task 12 on 11.
- Task 13 depends on 11 and 12; Task 14 on 13; Task 15 on 14;
  Task 16 on 12–15.
- Task 17 depends on 8 and 10; Task 18 on 5–8 and 17;
  Task 19 on 7, 10 and 14; Task 20 on 16–19.
- Task 21 depends on 1–20; Task 22 on 10, 19 and 21; Task 23 on 20–22;
  Task 24 on 23.
- Execution order follows the Phase Index. Dependencies state the minimum
  prerequisites, not permission to reorder verification checkpoints.

## Tasks

### Phase 1: Model contracts

- [x] Task 1: Define typed model hypotheses, models, and bounded state ([details](phase-01-model-contracts.md#task-1-define-typed-model-hypotheses-models-and-bounded-state)).
- [x] Task 2: Derive domain-specific hypotheses from admissible owner evidence ([details](phase-01-model-contracts.md#task-2-derive-domain-specific-hypotheses-from-admissible-owner-evidence)); depends on 1.
- [x] Task 3: Freeze prior predictions and deterministic predictive distributions ([details](phase-01-model-contracts.md#task-3-freeze-prior-predictions-and-deterministic-predictive-distributions)); depends on 1, 2.
- [x] Task 4: Implement observation-relative calibration, revision and comparison ([details](phase-01-model-contracts.md#task-4-implement-observation-relative-calibration-revision-and-comparison)); depends on 1, 3.

### Phase 2: Runtime and recovery

- [x] Task 5: Settle future outcomes from actual owner observations ([details](phase-02-runtime-and-recovery.md#task-5-settle-future-outcomes-from-actual-owner-observations)); depends on 1–4.
- [x] Task 6: Integrate staged cognition without adding action authority ([details](phase-02-runtime-and-recovery.md#task-6-integrate-staged-cognition-without-adding-action-authority)); depends on 5.
- [x] Task 7: Add strict predictive state and pending-finalization codecs ([details](phase-02-runtime-and-recovery.md#task-7-add-strict-predictive-state-and-pending-finalization-codecs)); depends on 1, 6.
- [x] Task 8: Preserve fork, retry, retirement and completed-run exports ([details](phase-02-runtime-and-recovery.md#task-8-preserve-fork-retry-retirement-and-completed-run-exports)); depends on 6, 7.

### Phase 3: Analysis and publication

- [x] Task 9: Normalize frozen owner forecasts into detached source facts ([details](phase-03-analysis-and-publication.md#task-9-normalize-frozen-owner-forecasts-into-detached-source-facts)); depends on 8.
- [x] Task 10: Add bounded analysis and six append-only metric families ([details](phase-03-analysis-and-publication.md#task-10-add-bounded-analysis-and-six-append-only-metric-families)); depends on 4, 9.
- [x] Task 11: Define canonical predictive snapshots and read/publication ports ([details](phase-03-analysis-and-publication.md#task-11-define-canonical-predictive-snapshots-and-readpublication-ports)); depends on 9, 10.
- [ ] Task 12: Compose and publish only after scientific completion ([details](phase-03-analysis-and-publication.md#task-12-compose-and-publish-only-after-scientific-completion)); depends on 11.

### Phase 4: Store, API and UI

- [ ] Task 13: Implement immutable quota-bounded filesystem storage ([details](phase-04-store-api-and-ui.md#task-13-implement-immutable-quota-bounded-filesystem-storage)); depends on 11, 12.
- [ ] Task 14: Add dual-gated GET-only scientific-model routes ([details](phase-04-store-api-and-ui.md#task-14-add-dual-gated-get-only-scientific-model-routes)); depends on 13.
- [ ] Task 15: Build the read-only Scientific Models panel ([details](phase-04-store-api-and-ui.md#task-15-build-the-read-only-scientific-models-panel)); depends on 14.
- [ ] Task 16: Prove end-to-end read isolation and authorization ([details](phase-04-store-api-and-ui.md#task-16-prove-end-to-end-read-isolation-and-authorization)); depends on 12–15.

### Phase 5: Experiments and regressions

- [ ] Task 17: Add an off-gate reproducible scientific-model experiment ([details](phase-05-experiments-and-regressions.md#task-17-add-an-off-gate-reproducible-scientific-model-experiment)); depends on 8, 10.
- [ ] Task 18: Add adversarial temporal and provenance regressions ([details](phase-05-experiments-and-regressions.md#task-18-add-adversarial-temporal-and-provenance-regressions)); depends on 5–8, 17.
- [ ] Task 19: Lock the supported configuration and compatibility matrix ([details](phase-05-experiments-and-regressions.md#task-19-lock-the-supported-configuration-and-compatibility-matrix)); depends on 7, 10, 14.
- [ ] Task 20: Verify scientific arithmetic, boundedness and a real runner artifact ([details](phase-05-experiments-and-regressions.md#task-20-verify-scientific-arithmetic-boundedness-and-a-real-runner-artifact)); depends on 16–19.

### Phase 6: Documentation and verification

- [ ] Task 21: Complete the mandatory documentation checkpoint ([details](phase-06-documentation-and-verification.md#task-21-complete-the-mandatory-documentation-checkpoint)); depends on 1–20.
- [ ] Task 22: Update current pins without rewriting historical contracts ([details](phase-06-documentation-and-verification.md#task-22-update-current-pins-without-rewriting-historical-contracts)); depends on 10, 19, 21.
- [ ] Task 23: Execute the final regression and quality gates ([details](phase-06-documentation-and-verification.md#task-23-execute-the-final-regression-and-quality-gates)); depends on 20–22.
- [ ] Task 24: Record implementation outcome and unresolved limitations ([details](phase-06-documentation-and-verification.md#task-24-record-implementation-outcome-and-unresolved-limitations)); depends on 23.

## Commit Plan

Suggested checkpoints only; no commits are authorized by this planning request.

1. After Tasks 1–4: `feat(science): define hypothesis-derived predictive models`
2. After Tasks 5–8: `feat(science): persist prior forecasts and recover model state`
3. After Tasks 9–12: `feat(analysis): publish qualified predictive performance`
4. After Tasks 13–16: `feat(research): inspect scientific models and calibration`
5. After Tasks 17–20: `test(science): prove forecast chronology and model comparison`
6. After Tasks 21–24: `docs(science): document predictive models and verification`

## Definition of Done

- All 24 tasks meet their linked acceptance criteria; this index alone tracks
  progress and records actual verification.
- Every scored prediction is immutable and finalized before its physical outcome;
  missing/late/noncomparable observations never become failures.
- Source/model revisions, predictive confidence, actual owner observations,
  calibration and paired comparison are inspectable with explicit coverage.
- Owner boundaries, deterministic continuation, pending recovery, forks,
  retirement and legacy/off-path contracts remain intact.
- All mandatory local Python/static/import/UI gates pass with coverage; required
  real runner/store/API tests execute and demonstrate at least three paired cases.
- Current metric catalog has exactly six appended families; no new world
  authority, context/flag, runner schema, replay pair, migration or Godot change.
- Documentation and current pins match implementation; historical contracts and
  unowned capabilities are not silently reinterpreted.
- Conditional certification lanes and domain limitations remain explicit.

## Planning Validation

Exploration covered cognition/runtime/recovery, observable target limits,
detached science contracts, publication/store/API/UI templates and focused test
commands. No implementation tests were run while planning. No code, source
requirements, branch, roadmap or configuration was changed.

Bundle integrity checked: one marker, six linked direct child phase files,
exactly 24 unique task headings/checklist links, valid local links and anchors,
no orphan files and no phase checkboxes. Task dependencies reference earlier
existing task IDs; rerun validation after any plan refinement.

## Open Questions and Limitations

No blocking architectural question remains for the bounded scope above.
Scientific limitations are deliberate: disease unavailable; resource
regeneration represented only by net observed change; production limited to
existing categorical experiments; predictive comparison is descriptive over
retained owner-observed matched cases, not proof of physical truth or causality.
Expanding those limits requires a separate scoped requirement, not implementer
guesswork.

## Refinement Record

2026-11-18 — `$aif-improve`; all six refinements approved by the user.
Task IDs/count, phase order, dependencies, settings and Original Request are
unchanged. Implementation has not started.

1. **Completed-result handoff:** Tasks 8–10/20 add validated
   `SimulationRunnerResult.scientific_model_ledgers` and real collector/builder
   coverage. Evidence: existing result science tuples, `runner.py` result
   construction and `experiments/collectors.py`.
2. **Blank-slate enforcement:** Tasks 6/8/19 name deny/store/count/probe edits
   and populated-versus-empty tests. Evidence: `new_agent_initialization.py`,
   `runner._blank_slate_counts`, `civilization_benchmark_evidence.py`, and
   `.ai-factory/patches/2026-11-17-23.37.md`.
3. **Runtime/fork precision:** Tasks 6–8 bind after final `loop_result.command`,
   use checkpoint-only committed state and include its digest. Evidence:
   `AgentRuntime.bind_effective_command`, `AgentRuntimeForkState`,
   `restore_fork_state` and `fork_state_digest`.
4. **Complete bounds/reference closure:** Tasks 1–4/9–11 lock nested caps,
   aggregated notices, complete-case selection and post-cap denominators.
   Evidence: planned reference graph, existing bounded science contracts and
   V4-19/V4-23 cap/coverage prevention records.
5. **Read/publication contracts:** Tasks 11–16 name cursor aliases, section
   filters, signed-publication selection, distinct missing errors, closed
   receipt states and real-factory multi-window tests. Evidence:
   `api/replication_cursor.py`, `api/routes/replication.py`, `api.app.create_app`,
   `experiments/replication_publication.py` and V4-28 prevention records.
6. **Source lifecycle:** Tasks 2–5/18 define suspension/resumption/retirement/
   replacement without altering issued forecasts. Evidence: existing
   `ExperimentHypothesis` statuses/revisions and the prior-prediction requirement.

## Next Command

`$aif-implement .ai-factory/plans/v4-30-scientific-models/index.md`
