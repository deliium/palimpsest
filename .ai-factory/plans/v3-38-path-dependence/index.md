<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V3-38 Historical Contingency Experiments

Mode: ultra
Canonical plan identifier: `v3-38-path-dependence`
Branch: `main` (existing; no branch/worktree created)
Created: 2026-10-23
Refined: 2026-10-23 (seven approved code-backed improvements; task IDs preserved)
Status: implemented; verification remediation applied (2026-10-24)

## Original Request

v3-38 historical contingency experiments

Plan naming requirement:

Use a `v3-` prefixed canonical plan identifier.

Suggested stem:

v3-38-path-dependence

Build experiments around forked replay to study historical contingency.

Example:

Common history until tick 100

Branch A:  
founder shares food

Branch B:  
founder refuses

Then continue for many generations.

Compare:

norms  
relationships  
institutions  
technology  
cultural narratives  
inequality  
cooperation

Support ensembles of small early interventions.

Do not claim causality from a single run.

Provide statistical comparison across repeated seeds/branches.

Track intervention lineage explicitly.

## Settings

- Testing: yes; unit/architecture coverage stays enabled; PostgreSQL and long-run gates are opt-in and skips are disclosed.
- Logging: verbose, metadata-only; no credentials, command payloads, subjective content, raw exceptions or content-digest surrogates.
- Docs: yes; mandatory `$aif-docs` checkpoint during implementation.
- Language: English artifacts/UI; preserve technical terms.
- Git: enabled, base `main`, `create_branches=false`; planning changes only.
- Verification: normal workflow default; hard scientific/authority gates below are mandatory.
- Provider scope: deterministic fake only; no live/record/cache/recorded-replay fork execution in v1.
- Research source: none; configured RESEARCH and research bundles are absent. Code reconnaissance is evidence, not an invented research artifact.

## Roadmap Linkage

Milestone: "M7 — V3 Generational Civilization"

Rationale: Adds reproducible forked-history, multigeneration experimental comparison over existing owned V3 seams without owning `institutional_economy` or claiming scripted institutional emergence.

M6/M7 remain open. Roadmap is a scope indicator; historical counts in its older paragraphs are not current pins. Milestone edits/registration belong to `$aif-roadmap`, not this planning invocation.

## Scope and Success

Implement a trusted grouped research protocol, Experiment **BN** / `historical_contingency@1`, which executes a common prefix, captures complete objective and owner-local state at finalized boundary F, materializes independent child replay journals, applies small child-only ordinary commands, and continues to absolute horizon H across generations.

The food example operationalizes sharing as an admitted `Give` of a named portable food item, and withholding as `Wait` for that actor/tick. It does not invent an explicit refusal utterance, moral trait or global norm. Noop/untouched arms are real replay children, not mislabeled fresh simulations. Multiple actions are one predeclared compound protocol, not automatically identified independent causes.

The long demonstration uses F=100/H=1100; F is the next tick, so ticks 0–99 are common and tick 100 is the first possible intervention. Smoke tests use F=4/H=36. Both use the explicit `bn-food-opportunity-v1` fixture: named possessed food, co-located founders, declared benign physical rules/regenerating resources, common pre-F command setup and exact non-preempting generation stops. They do not inherit BM's empty inventories, separated founders, exhausted resources or default generation-stop limit. These shared physical choices make the demonstration executable; they do not install social knowledge or guarantee social effects. Arbitrary user scenarios still undergo honest eligibility checks. Scenarios must actually permit post-F generations and founder turnover; zero/unknown effects are valid outcomes. Ineligible prefixes are reported, never fixed by outcome-driven reseeding or hidden state edits.

### Explicit non-goals

- No new capability flag/ownership, institution type, global society registry, world action/event, observer semantic, API route, migration or runtime dependency.
- No runner v56, result schema change, replay/codec bump or metric family addition; sibling experiment/comparison artifacts only.
- No nested/adaptive fork trees, belief/memory patches, world-state editing or automatic intervention search.
- No generic matrix cells pretending to share a prefix; grouped executor is separate and `prepare_parallel=False` remains.
- No durable full-subjective checkpoint wire format. Full fork state is process-local; process-loss recovery re-executes and validates the deterministic prefix.
- No automatic retry/substitution of an already-created durable child under a new RunId. Resume adopts exact completed children or reconstructs a sealed prefix to launch unused planned slots; partial durable children stay failed/missing.
- No live or recorded-replay LLM forks until provider state/recording identity continuation is separately owned.
- No common-random-number guarantee for run-ID-scoped channels; no redefinition of legacy derivation-v3.
- No single-run causal claim, automatic causal conclusion from a confidence interval, global culture score, p-values or winner rankings.

## Requirements Reconciliation

Authority: root `AGENTS.md` and `.ai-factory/RULES.md` / `rules/base.md` govern exploration and implementation; user request defines feature scope; `.ai-factory/ARCHITECTURE.md` defines authority/versioning boundaries. Executable codecs/algorithms establish current behavior. Roadmap/descriptive summaries are scope indicators, not permission to violate those contracts. No unresolved source conflict changes implementation scope.

| Decision / supported combination | Source path and section | Verification evidence |
|---|---|---|
| Canonical identifier starts `v3-`; no branch creation | Original Request; `.ai-factory/config.yaml` — git/workflow | Bundle path and Git status; Task 18 discovery guidance. |
| Complete common subjective history, not objective-only seek | Original Request; `docs/generational-runner.md` — historical inspection; `runner.py` — checkpoint application | Tasks 3–6: complete owner state/roster and uninterrupted continuation parity. |
| Runtime sets, legacy stores and fresh-empty coverage are part of complete state | `agent_runtime.py:398–495`, `3130–3303`, `3942–3987`; `runner.py:2315–2393` | Tasks 3–6: actual deduplication IDs/counters, legacy beliefs and known-empty channel restore. |
| Collectors must be installed before restored started/cursor state | `runner.py:3143–3154`; `cultural_evidence.py:119–137` | Tasks 4, 9–10: factory-installed sink, one F baseline and F+1 next publication. |
| Demonstration needs an explicit physical fixture and shared setup | `regional_migration_scenario.py:225–272`; `generational_comparison_base.py:77–134` | Tasks 1, 8, 16: named food/custody/co-location, resources, modes and horizon/generation-stop tests. |
| `WorldEngine` admits all treatment commands | `RULES.md` axioms 1–3; ARCHITECTURE — Objective authority | Task 7 rejection/acknowledgement tests. |
| Existing fork snapshot omissions must be fixed before reuse | `persistence.py:603–639` vs `branch_service.py:377–477` | Task 2 regression for genealogy, needs and repositories. |
| Independent unit is root numeric-seed block, not branch/agent/tick | Original Request; `cultural_metric_comparison.py` — repeated-seed numerical policy | Task 12 hand-calculated paired/block tests; duplicate seeds retain n=1. |
| Seven separate outcome domains, exact keys and zero policies | Original Request; existing analysis algorithm definitions | Tasks 10–12 selector/coverage fixtures and direct-calculator oracles. |
| Legacy institution PARTIAL/ABSENT is not universally missing or known zero | `institutional_persistence.py:190–269`; cultural metric coverage semantics | Task 11 explicit complete-empty-search witness tests. |
| Child run IDs can alter channels despite shared objective stochastic identity | `randomness.py:78–107`; `generational_seeds.py` | Task 5 treatment-blind randomized slots and all-pair channel accounting. |
| No new feature runner schema/flag or authoritative institution semantics | ARCHITECTURE — Versioned Extension Contract | Task 17 current/legacy pins and fail-closed unowned flags. |
| Source digests and lineage independently verified, never self-attested sidecars | Existing cultural/generational artifact contracts; Original Request | Task 13 transplant/tamper/wrong-expected-ID tests. |
| Prefix paths distinguish F; technical failure never seals as completion | Multi-F spec; `generational_execution.py` failure classifier; 2026-10-22 patch prevention rules | Tasks 9, 13–16: boundary-qualified paths, stage crash tests and completion/failure exclusivity. |
| Partial durable child identity is never replaced during resume | `generational_seeds.py` actual run-ID scopes; existing matrix `durable_origin_rerun_unsupported` contract | Tasks 5, 12–16: original slot RunId validation and failed-partial outcomes. |
| BN is a separate typed grouped catalog, not ordinary independent cells | `models.py:70–120`; `catalog.py:2754–2784`; `coordinator.py:145–181`; `matrix_runner.py:300–314` | Tasks 8, 15, 17: registry and guards before expansion, writes or resume/adoption. |
| Mandatory docs and M7 linkage | Confirmed planning preferences | Task 18 docs checkpoint; no roadmap closure. |

### Supported behavior combinations

| Input / state | Validation and persisted evidence | Output / transition and side effects | Verification |
|---|---|---|---|
| v55, fake provider, finalized F, fork-capable owner bundles | Exact config/roster/owner-state, F/revision/head; prefix artifact | Complete child restore; ordinary continuation; immutable parent | Tasks 4, 6, 9. |
| F=0 after initialization vs F>0 | Fully published baseline; strict `event.tick < F` prefix | Same absolute tick convention; no early treatment | Tasks 2, 4, 6. |
| Historical objective archive without full live owner state | Sealed eligible prefix and original history required; child RunId must not yet exist | Reconstruct parent from tick zero and compare complete digest to launch unused slot, or block | Task 14. |
| Pending/terminal/inconsistent boundary | Safe failure code; no sealed prefix | Reject capture before child creation | Task 4. |
| Eligible named food opportunity | Frozen founder/item/recipient witness before treatment | Share/withhold schedules resolved through normal admission | Tasks 7–9. |
| Missing/dead founder, invalid custody or no recipient | `prefix_ineligible` witness and denominator | No branch at that F; no reseeding or silent substitution | Task 8. |
| Give applied vs rejected/missed; Wait; untouched | Requested/effective/committed ledger per action | Assigned-arm analysis primary; no later retry to force exposure | Tasks 7, 12. |
| Several small actions or F values | Per-F arm schedules and budgets; named protocol contrasts | Separate contrasts, single seed block for dependent histories | Tasks 1, 9, 12. |
| One seed or duplicate seed labels/replicas | Full slot/block membership | Descriptive mean; n=1; no CI; explicit illustrative warning | Tasks 5, 12, 15. |
| Multiple independent seeds, compatible measured pairs | Checkpoint/config/outcome/provider/source compatibility | Paired differences, numeric-seed block means, pointwise Student-t CI | Task 12. |
| Missing/censored/disabled outcome vs verified complete-empty | Domain-specific coverage and reason codes | Exclude unknown pair; known zero only with selector witness; report attrition | Tasks 10–12. |
| Mixed/unknown post-F stream alignment | Compare actual channel manifests for every pair | Qualified comparison or descriptive status; never claim same-noise isolation | Tasks 5, 12. |
| Live/replay LLM provider or stochastic init/lifespan profile | Preflight unsupported-provider/random-policy code | Reject, no fake fallback or reinterpretation of legacy streams | Tasks 4–5, 15. |
| Completed valid branch vs unused slot vs incomplete durable child | Root/prefix/assignment/terminal seal plus actual child-run existence | Adopt completion; reconstruct prefix for never-created slot; existing partial child stays failed/missing with no replacement | Tasks 13–15. |
| Same parent has several F values | F is in prefix path, digest and lineage identity | Independent immutable prefix records for each F, all within one numeric-seed block | Tasks 1, 13–16. |
| Capture F=0 or restored F>0 with a cultural sink | Initialize boundary zero explicitly; install sink before started/cursor restore | Exactly one complete F baseline with preserved empty/unknown channel status, then F+1 | Tasks 4, 6, 10. |
| Tampered source/lineage/schedule/outcome artifact | Independently derived expected identity, hashes and path safety | Fail verification; never repair sealed artifacts | Tasks 13, 16. |

## Architecture and Decisions

### Ownership and data flow

1. **Simulation** owns complete finalized checkpoint capture/restore and typed owner/run scope rebasing. Memory/social packages own their immutable service state contracts. Existing branch service rematerializes objective journals; only child-head replay yields a writable engine.
2. **Experiments** owns predeclared designs, random arm assignment to treatment-blind slots, eligibility, bounded command arbiters, grouped execution, evidence collection, artifact verification and lineage. It imports no concrete persistence or API.
3. **Analysis** owns detached seven-domain scalar projection and paired seed-block statistics; it receives no live runtime/DB/services. Existing metrics are reused, not relabeled as global cultural truth.
4. **Research runner** composes actual PostgreSQL repositories, isolated prefix-reconstruction repositories, in-memory fork-capable subjective services and CLI. No HTTP or client changes.

Flow: strict spec → seal design/slot assignment/common setup → initialize parent boundary zero and run to finalized F → freeze full checkpoint and seal boundary-qualified eligibility → seal preparation with original child identity → rematerialize child objective prefix → construct child with sinks installed before restoration → restore child head/full owner state and publish one F baseline → normal command treatment/admission → production cognition through H → classify technical failure vs scientific stop → seal evidence/result then completion LAST, or failure only → independently verify all input identities → paired seed-block comparison.

### Complete-state and replay limitations addressed

The existing `apply_runtime_checkpoint()` restores cursors/known runtimes but not objective state or missing admitted runtimes; `rebase_runtime_checkpoint()` changes only outer run ID. Existing `SubjectiveOwnerSnapshot` omits memory reconstruction/access operations, belief/relationship histories and commit receipts. The new strict API must close these gaps, not hide them behind a shallow clone. Existing incomplete legacy clone APIs retain their narrower contracts.

Complete fork state includes the ordered admitted/retired roster, all runtime cultural/cognitive ledgers, legacy belief/memory stores, actual processed/finalized identity sets (not only counts), invocation/goal revision counters, applied reflection/identity receipts, semantic cultural fresh-empty/completeness witnesses, owner stores/histories/idempotency state, initialized parameters, finalized receipts, population progress and control state. New `AgentRuntimeForkState` wraps rather than silently widening the existing durable checkpoint. Every runtime slot is classified as immutable configuration, reconstructed resource or captured state. No newborn receives founder content. No clients/locks/providers/sessions are copied. A same-RunId isolated test restore must exactly match uninterrupted execution; production distinct-ID children must match their common pre-treatment state and repeated same-child execution in isolated TEST repositories, with documented post-F identity noise. Full outcome/evidence parity is checked at Task 16, after outcome collectors exist, rather than creating a circular prerequisite for Task 6.

Restoration receives its cultural sink before applying started/cursor state. The factory publishes exactly one verified boundary-F baseline after complete owner restoration; it does not call the current pre-start-only setter afterward or classify known-empty ledgers as missing. Boundary-zero initialization has an explicit public no-tick method. Existing narrower legacy restore/capture behavior remains compatible.

### Identity, inference and interpretation

Run IDs are opaque treatment-blind slots derived from a separate label-free design fingerprint. Assignment uses an explicit injected seeded stream and is sealed before post-F outcomes. Original numeric seeds define independent blocks; replicas, duplicate seeds and multiple forks do not inflate n. Existing channel semantics remain unchanged. Channel comparison checks all included pairs, not the first one.

One planned slot has one scientific child RunId. A sealed valid completion may be adopted. A sealed eligible parent prefix can be deterministically reconstructed in isolated repositories to launch a slot whose original RunId was never created. A child already created without valid completion remains failed-partial/missing; no new-RunId retry can fill it or become the preferred successful attempt. Missing/corrupt expected prefix state blocks reconstruction, and a new scientific rerun requires an explicitly new ensemble. Comparison retains all failure/eligibility denominators and labels incomplete designs accordingly.

Primary contrasts are treatment minus control within a matched prefix/F/replicate, then averaged within numeric seed, then equally across independent seeds. At n≥2 report sample SD/SE and pointwise 95% Student-t CI; n=1 remains descriptive with no interval. No p-values or familywise significance claim. Missing pairs and post-treatment attrition are disclosed; applied-only treatment subsets cannot replace assigned-arm results. `causal_claim` is always false in v1.

### Compatibility and rollout

Default runner/result remain v4/v2; latest feature runner stays v55. Feature-selected replay-v22/codec-v20, 43 commands, 73 semantic types, 136 metric families, Alembic `0017`, `/v1` and `observer-protocol-v1` remain unchanged; preserve every legacy accepted version. Both unowned flags remain fail-closed. New schemas are separate research siblings with exact-key codecs, not extra runner fields.

CLI rollout is opt-in `palimpsest-matrix path-dependence ...`. BN discovery uses a separate typed grouped registry, not an unversioned `ExperimentDefinition` metadata extension; coordinator and matrix entry points reject grouped identity before assignments, writes and skip/adoption paths. Initial execution is serial, fake-only, deterministic distributions, bounded static star forks and fixed endpoint/cohort windows. Unsupported configurations fail before prefix writes. Completed artifacts are immutable; restart either adopts verified completion or regenerates exact parent prefix state for an unused slot, never invents partial-child subjective restart.

## Phase Index

1. [Phase 1: Contracts and complete fork state](phase-01-contracts-and-state.md) — Tasks 1–3
2. [Phase 2: Finalized-boundary replay continuation](phase-02-fork-continuation.md) — Tasks 4–6
3. [Phase 3: Intervention ensembles](phase-03-intervention-ensembles.md) — Tasks 7–9
4. [Phase 4: Outcomes and inference](phase-04-outcomes-and-inference.md) — Tasks 10–12
5. [Phase 5: Artifacts, resume and CLI](phase-05-artifacts-resume-and-cli.md) — Tasks 13–15
6. [Phase 6: Gates and documentation](phase-06-gates-and-documentation.md) — Tasks 16–18

## Cross-Phase Dependencies

- Task 2 depends on Task 1's declared boundary/identity contract; Task 3 uses Task 1's frozen state/ownership constraints.
- Task 4 depends on Tasks 2–3; Task 5 depends on Tasks 1 and 4; Task 6 depends on Tasks 2–5 and blocks experimental execution claims.
- Task 7 depends on Tasks 1 and 6; Task 8 depends on Tasks 1 and 7; Task 9 depends on Tasks 4–8.
- Task 10 depends on Tasks 4 and 9; Task 11 depends on Task 10; Task 12 depends on Tasks 5, 10–11.
- Task 13 depends on Tasks 1, 5, 9–12; Task 14 depends on Tasks 6, 9, 13; Task 15 depends on Tasks 9 and 12–14.
- Task 16 depends on Tasks 1–15; Task 17 depends on Task 16; Task 18 depends on Tasks 15–17.
- Execute tasks sequentially; early tasks can use in-memory sink test doubles until Task 13 supplies durable storage. No phase advertises a production-complete workflow before Task 15.
- Task 6 proves full state/trajectory parity with no dependency on later analytics. Task 16 adds full metric/evidence parity after Tasks 10–12. Task 14 owns isolated reconstruction adapter implementation; Task 15 only composes it into the CLI, avoiding a backwards implementation dependency.

## Tasks

### Phase 1: Contracts and complete fork state

- [x] Task 1: Define historical-contingency experiment contracts ([details](phase-01-contracts-and-state.md#task-1-define-historical-contingency-experiment-contracts))
- [x] Task 2: Preserve complete objective state during rematerialization ([details](phase-01-contracts-and-state.md#task-2-preserve-complete-objective-state-during-rematerialization)) (depends on 1)
- [x] Task 3: Export and restore complete owner service state ([details](phase-01-contracts-and-state.md#task-3-export-and-restore-complete-owner-service-state)) (depends on 1)

### Phase 2: Finalized-boundary replay continuation

- [x] Task 4: Capture and restore coherent runner fork checkpoints ([details](phase-02-fork-continuation.md#task-4-capture-and-restore-coherent-runner-fork-checkpoints)) (depends on 2, 3)
- [x] Task 5: Rebase typed scope and record truthful branch identities ([details](phase-02-fork-continuation.md#task-5-rebase-typed-scope-and-record-truthful-branch-identities)) (depends on 1, 4)
- [x] Task 6: Prove replay and no-treatment continuation equivalence ([details](phase-02-fork-continuation.md#task-6-prove-replay-and-no-treatment-continuation-equivalence)) (depends on 2, 3, 4, 5)

### Phase 3: Intervention ensembles

- [x] Task 7: Apply bounded interventions through ordinary admission ([details](phase-03-intervention-ensembles.md#task-7-apply-bounded-interventions-through-ordinary-admission)) (depends on 1, 6)
- [x] Task 8: Define Experiment BN and pre-treatment eligibility ([details](phase-03-intervention-ensembles.md#task-8-define-experiment-bn-and-pre-treatment-eligibility)) (depends on 1, 7)
- [x] Task 9: Execute shared prefixes and isolated child continuations ([details](phase-03-intervention-ensembles.md#task-9-execute-shared-prefixes-and-isolated-child-continuations)) (depends on 4, 5, 6, 7, 8)

### Phase 4: Outcomes and inference

- [x] Task 10: Collect bounded finalized evidence with exact coverage ([details](phase-04-outcomes-and-inference.md#task-10-collect-bounded-finalized-evidence-with-exact-coverage)) (depends on 4, 9)
- [x] Task 11: Register exact scalar outcomes for all requested domains ([details](phase-04-outcomes-and-inference.md#task-11-register-exact-scalar-outcomes-for-all-requested-domains)) (depends on 10)
- [x] Task 12: Compare paired protocols across independent seed blocks ([details](phase-04-outcomes-and-inference.md#task-12-compare-paired-protocols-across-independent-seed-blocks)) (depends on 5, 10, 11)

### Phase 5: Artifacts, resume and CLI

- [x] Task 13: Seal explicit intervention lineage and outcome artifacts ([details](phase-05-artifacts-resume-and-cli.md#task-13-seal-explicit-intervention-lineage-and-outcome-artifacts)) (depends on 1, 5, 9, 10, 11, 12)
- [x] Task 14: Resume by verified adoption or deterministic reconstruction ([details](phase-05-artifacts-resume-and-cli.md#task-14-resume-by-verified-adoption-or-deterministic-reconstruction)) (depends on 6, 9, 13)
- [x] Task 15: Add researcher CLI composition and comparison commands ([details](phase-05-artifacts-resume-and-cli.md#task-15-add-researcher-cli-composition-and-comparison-commands)) (depends on 9, 12, 13, 14)

### Phase 6: Gates and documentation

- [x] Task 16: Prove the full historical-contingency experiment workflow ([details](phase-06-gates-and-documentation.md#task-16-prove-the-full-historical-contingency-experiment-workflow)) (depends on 1–15)
- [x] Task 17: Enforce scientific, authority and compatibility regression gates ([details](phase-06-gates-and-documentation.md#task-17-enforce-scientific-authority-and-compatibility-regression-gates)) (depends on 16)
- [x] Task 18: Document reproducibility, interpretation and the new experiment seam ([details](phase-06-gates-and-documentation.md#task-18-document-reproducibility-interpretation-and-the-new-experiment-seam)) (depends on 15, 16, 17)

## Commit Plan

- **Commit 1**, after Tasks 1–3: `feat(simulation): define complete owner-safe fork state contracts`
- **Commit 2**, after Tasks 4–6: `feat(simulation): restore finalized replay forks with full runtime state`
- **Commit 3**, after Tasks 7–9: `feat(experiments): execute historical contingency branch ensembles`
- **Commit 4**, after Tasks 10–12: `feat(analysis): compare historical branch outcomes by seed block`
- **Commit 5**, after Tasks 13–15: `feat(research-runner): persist and resume historical contingency ensembles`
- **Commit 6**, after Tasks 16–18: `test(experiments): gate and document historical contingency workflows`

These are suggested implementation checkpoints, not authorization to commit or push during planning.

## Definition of Done

- Every task is implemented and verified; Phase Index links/task mappings remain intact, and only this file records task progress.
- Exact common prefix/full-owner-state and no-treatment continuation gates pass, including previously admitted agents, modern snapshot fields, prior-event observations and owner-store idempotency/history.
- Eligible share/withhold children are actual replay forks; interventions use ordinary admission and committed exposure is not confused with assignment.
- Long and smoke profiles permit and demonstrate post-F generations without scripted social effects; ineligibility and zero/unknown differences are reported honestly.
- All seven outcome domains have explicit selector/evidence/coverage/window semantics; no missing value becomes zero without a domain witness.
- Repeated-seed comparison reports paired/block arithmetic, independent n, membership, exclusions, pointwise intervals and stream/attrition limits. Single numeric seed never produces an inferential interval or causal claim.
- Source/prefix/intervention/slot/attempt/outcome lineage is sealed and independently verified, with separate paths for every F and explicit preparation/result/completion/failure kinds. Completion and technical failure are mutually exclusive. Resume adopts completed artifacts or proves deterministic full-prefix reconstruction for an unused planned child; no partial durable-child append, replacement scientific identity or subjective restart is implied.
- Default/legacy schemas, authority boundaries, flags-off regressions, unowned flags, current counts and client/API contracts remain intact.
- Unit/architecture/lint/type/import gates pass with coverage; actual PostgreSQL and long-run validation are executed or explicitly disclosed as verification gaps.
- Mandatory docs checkpoint completes; roadmap changes go through their owner and do not close M6/M7.

## Risks and Deferred Work

- Complete subjective continuation is substantial prerequisite work; Tasks 3–6 are not optional. If a newly discovered unsupported state cannot be copied exactly, fail preflight and amend this plan before claiming support.
- Distinct child identity creates documented stochastic/identity noise. Randomized treatment-blind slots reduce systematic assignment confounding; they do not create pathwise common random numbers or establish a real-world causal estimand.
- The default food-opportunity fixture deliberately uses benign shared physical conditions and an explicitly scripted common prefix; report that conditioning rather than generalizing its results to arbitrary resource ecologies. Newborn institution concepts remain disabled under the existing developmental species profile and coverage must disclose that restriction.
- Founder opportunity selection conditions the experiment on eligible prefixes; report both eligibility denominator and complete-pair attrition. Do not generalize automatically to all generated societies.
- Nonparametric/cluster-bootstrap sensitivity analysis, multiplicity-controlled confirmatory testing, nested fork trees, recorded-LLM fork state and versioned unified branch stochastic identity are deferred, not hidden implementation choices.
- No blocking design question remains for this bounded v1 plan. Infrastructure availability may block execution verification, not justify a false passing result.

## Implementation Entry Point

Run `$aif-implement .ai-factory/plans/v3-38-path-dependence/index.md` explicitly: branch creation is disabled and the repository may contain several other plans. Read this index and the complete linked phase before executing its tasks.
