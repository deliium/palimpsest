<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V3-37 Cultural Evolution Metrics

Mode: ultra  
Branch: main (stay on current branch; automatic branch creation disabled)  
Created: 2026-10-23  
Plan identifier: `v3-37-cultural-metrics`  
Status: planned; implementation not started

## Original Request

v3-37 cultural evolution metrics

Plan naming requirement:

Plan filename/bundle directory MUST begin `v3-`.

Suggested stem:

v3-37-cultural-metrics

Implement quantitative cultural evolution metrics.

Measure where applicable:

trait frequency  
trait persistence  
trait mutation  
trait extinction  
transmission fidelity  
horizontal transmission  
vertical/intergenerational transmission  
between-group divergence  
within-group convergence  
cultural diversity  
narrative persistence  
vocabulary divergence  
technology retention  
technology loss

Avoid reducing all culture to one score.

Maintain provenance to underlying agent-level evidence.

Support confidence intervals and repeated-run comparison.

## Settings

- Testing: yes; deterministic unit, architecture, representative real-scenario integration and full default suite; retain coverage.
- Logging: verbose, metadata-only; safe IDs/counts/status/reason codes, never labels, fingerprints, messages, memory, prompts or evidence payloads.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 15.
- Language: English UI/artifacts; keep technical terms.
- Git: enabled, base `main`, no branch/worktree creation, no automatic commit or push.
- Verification: normal configuration default, with explicit scientific/compatibility gates below.
- Capture: composition-only and opt-in; default off. No new simulation config version or flag.
- Analysis window: exact baseline boundary (default 0) and optional exact endpoint (default actual last finalized boundary); empty/missing baselines are never silently rebased.
- Research: no research artifact exists; no external research or historical plan was used as a requirement source.

## Roadmap Linkage

Milestone: "M7 — V3 Generational Civilization"  
Rationale: Adds detached quantitative evaluation of generational cultural continuity, transmission and divergence using already owned V3 seams; does not own institutional economy or close M7.

## Requirements Reconciliation

Authority: explicit user scope together with project axioms and architecture boundaries. Roadmap is a direction/status indicator, not a detailed behavioral contract. Existing source contracts constrain compatibility, not an obligation to reuse scientifically different estimands under old names.

| Decision / supported combination | Source path and section | Verification evidence |
|---|---|---|
| All 14 requested measurement areas, separate dimensions; no culture score | Original Request above | Tasks 4–9; Task 14 known-lineage fixture |
| Agent-scoped provenance, observational analysis only | `.ai-factory/RULES.md` axioms 1–6; `.ai-factory/ARCHITECTURE.md` §§Dependency Rules, Memory/testimony | Tasks 1–3, 11, 14 boundary/provenance tests |
| Default-off behavior and accepted legacy writes remain unchanged | `.ai-factory/ARCHITECTURE.md` §Versioned Extension Contract | Tasks 2, 10, 14; V1 and scientific gates |
| Audit occurrences do not establish current possession | `src/agents/cognition/cultural_features.py` — `CulturalFeatureAudit`, `CulturalFeatureLedger`; `src/analysis/cultural_traits.py` — `compute_analytical_cultural_traits` | Tasks 1–4 boundary inventory tests |
| Modalities do not establish donor edges or kinship | `src/agents/cognition/cultural_features.py` — public uptake cues; `src/agents/cognition/practical_knowledge.py` — source/teacher/parents | Tasks 3, 5 attribution tests |
| Preserve old narrative/semantic/lifecycle algorithms; introduce new estimands | `src/analysis/cultural_narrative_metrics.py`, `generational_narratives.py`, `semantic_drift_metrics.py`, `technique_lifecycle.py` | Tasks 7–10; legacy tests unchanged |
| P05/p95 are distribution ranges, not mean CIs | `src/analysis/distribution_summary.py`, `matrix_metric_summary.py`; `docs/experiments.md` — matrix summaries | Task 12 analytical t-reference tests; Task 15 interpretation |
| Duplicate seeds/replicas must not inflate independent sample size | `src/experiments/models.py` — `ExperimentSeedMatrix`; `coordinator.py` — `materialize_assignments` | Task 12 seed-block/pair tests |
| Valid completion + bound evidence required for comparison | `src/experiments/matrix_manifest.py` — completion fingerprints; `matrix_runner.py` — sidecars | Tasks 11–13 stale/missing/corrupt artifact tests |
| Current count is 130 before this plan, 136 afterward | `src/analysis/specifications.py` — `METRIC_FAMILY_COUNT`; `.ai-factory/ARCHITECTURE.md` — V3-36 baseline | Task 10 catalog validation. Roadmap's dated 103 and DESCRIPTION's historical counts remain historical, not current pins. |
| Representative real integration, not only invented evidence | `src/experiments/generational_comparison_scenario.py`, `generational_comparison_base.py`; existing V2 fixture | Task 14 real three-seed BM-derived matrix and legacy fixture |
| Enabled, disabled, fresh-empty and restored-missing inventories are distinct | `src/simulation/agent_runtime.py` — `_commit_cultural_features`, `_commit_practical_knowledge` | Tasks 1–3 explicit per-channel coverage and runner-owned failure-status tests |
| Recovery publication follows entrant synchronization, not merely finalization/start | `src/simulation/runner.py` — `recover_pending_finalizations` 2936–3111 | Tasks 2, 14 real checkpoint/pending recovery, no fabricated boundary 0 |
| Pairing by seed does not prove shared random streams | `src/simulation/generational_seeds.py` — `build_generational_seed_manifest`; `src/experiments/generational_comparison_base.py` — deterministic distribution checks | Task 12 channel alignment and one-factor rematerialization tests |
| Artifact integrity includes duplicate keys, symlinks and every completion path | `src/experiments/generational_artifacts.py` — duplicate-aware JSON/safe-tree writes; `src/experiments/matrix_runner.py` — skip/adoption/completion paths | Tasks 11–14 corruption, fault injection and no-rerun tests |

### Supported combinations and availability

| Input/state | Validation / stored evidence | Output and side effects | Verification |
|---|---|---|---|
| Capture disabled, any existing runner version | Existing validation only; no new sidecars | Legacy metrics unchanged; six new families omitted | Tasks 2, 10, 14 |
| Capture enabled, channel disabled | Record disabled coverage explicitly | No claimed empty culture; other enabled dimensions still compute | Tasks 1, 4, 10 |
| Enabled channel, complete empty inventory, nonempty eligible population | Explicit empty rows + full owner coverage | Known zero richness/carriage; zero opportunities yield null fidelity/retention | Tasks 4, 5, 9 |
| Partial owners, missing baseline/frame, truncation/recovery prefix gap | Persist observed roster, gaps and coverage | Null exact prevalence/continuity/extinction where unidentifiable; eligible complete endpoint rows still usable | Tasks 2, 4, 11 |
| No living eligible population | Complete population evidence | `population_empty`; no inferred extinction | Tasks 4, 9 |
| Resolved same-generation donor, lower-generation teacher, explicit parent, unknown donor | Preserve source/recipient/kin evidence and class separately | Horizontal/intergenerational/kin-vertical counted distinctly; unknown excluded with denominator | Tasks 3, 5 |
| Explicit comparable donor/recipient fingerprints versus incompatible representations | Hash exact canonical source content; preserve comparability reason | Exact fidelity/mutation only for comparable single-source edges | Tasks 3, 5 |
| No groups / known groups / dynamic groups without alignment | Explicit partition/basis/tick membership; reject overlap | Global trait metrics available without groups; point divergence or aligned-cohort change only | Tasks 6, 8 |
| Living knowledge absent but records present/unknown | Distinct holder/record coverage | Living loss separate from global loss; unknown archives cannot prove global loss | Task 9 |
| n=0/1/2+ independent seeds, duplicate seed values/replicas | Verified artifacts and block membership | Null / point-only / Student-t mean CI; block count never raw cell count | Task 12 |
| Explicit paired conditions with missing counterpart | Pair ordinal/replicate, verify seed/stochastic/design identity | Complete-pair treatment-minus-control only, with exclusions | Tasks 12, 13 |
| Legacy completed cell with requested cultural capture missing | Valid objective completion, missing capture status | Report gap; no automatic rerun/backfill/overwrite | Tasks 11, 13 |
| Ordinary versus archived generational execution | Same composition option, separate existing run path | Same cultural sibling artifacts; no sealed archive/runner schema change | Tasks 11, 13, 14 |
| Exact nonzero/empty/missing baseline, explicit endpoint not reached | Persist requested and resolved window; no fallback to first available/nonempty frame | Cohort shares null for empty/missing baseline; independent complete point measurements remain usable | Tasks 1, 4, 7, 9, 13, 14 |
| Fixed owners but pair eligibility differs across endpoints | Freeze pairs with observed nonempty union at both endpoints | Same pair denominator for both endpoint means; excluded-pair counts visible | Tasks 6, 14 |
| Equal seed/stochastic identity, sampled run-ID-scoped channels differ | Persist actual stream selectors; no seed/config rewrite | Paired seed-block contrast labeled mixed alignment, not common random numbers | Task 12 |
| Multiple changed matrix factors or hidden config mutation | Re-materialize expected configs from selected registered factor levels | Reject requested contrast; do not widen the compatibility whitelist | Tasks 12, 13 |
| Artifact write fails after objective archive seals | No new capture-valid completion; preserve sealed archive and record research failure | No automatic rerun/adoption pretending to recover absent capture | Tasks 11, 13, 14 |

## Architecture and Decisions

### Data flow

`owner ledgers after complete finalization -> neutral simulation export -> bounded trusted experiment recorder -> post-run normalization + population/kinship/optional record/group evidence -> six analysis families -> canonical metric documents + resolvable evidence sidecars -> verified completed-cell loader -> seed-block summaries / explicit paired contrasts`.

- The recorder only stores immutable exports during execution. Analysis runs after the run and cannot alter commands, perception, world, stop criteria or memory.
- Capturing final ledgers alone cannot reconstruct continuous history. Capture boundary 0 and each completed boundary; missing intervals remain censored.
- Fresh execution captures boundary 0 only after proving no pending work. Restoration preserves the installed sink but starts an explicitly missing-prefix capture at the actual complete restored boundary. Runner-owned capture status survives exporter/sink failures and is merged into the research artifact.
- Expected populations include admitted newborns and exclude deceased owners from current prevalence; dead owners remain available as provenance sources.
- Representations are intentionally separate. Feature-carriage, vocabulary, narratives and practical knowledge never collapse into one latent score.
- Six new families are listed in Phase 4; 130 → 136 is the only catalog cardinality change. Existing scalar metric schema accommodates detail as canonical `rows_json`.
- Task 1 freezes exact measurement fields/units/denominator codes and separates formula keys from row identities. Task 3 provides canonical normalized-evidence encoding and its digest before metric assembly in Task 10; Task 11 only persists that same evidence and its bound documents.
- New artifacts: `cultural-evolution-evidence-v1`, `cultural-cell-metrics-v1`, `cultural-metric-comparison-v1`. Existing `matrix-metric-summary-v1`, `matrix-aggregate-v1`, runner and generational archive schemas retain their exact meaning. (`rows_json` contains typed measurements, not a fourth standalone schema.)
- New statistics use Student-t intervals over distinct numeric-seed blocks, with replicate/duplicate-seed averaging inside each block; confidence defaults to 0.95. Paired contrasts operate on matched differences before seed blocking. No p-values, automatic causal interpretation or false independence over agents/ticks.
- Paired v1 contrasts differ in exactly one declared matrix factor, verified by re-materializing both expected configs through the registered applicators. Actual per-channel random identity determines shared/mixed/unknown stream alignment; seed blocking is not a claim of identical draws across arms.
- No new capability ownership, experiment catalog ID, runner v56, result version, command, event, replay marker, codec, migration, API endpoint, observer semantic type or client feature. Defaults stay runner v4/result v2; existing feature-selected v55/result v3 remains supported. Counts stay 43 commands and 73 semantic types; latest replay-v22/codec-v20 remains feature-selected; migration head stays `0017`.
- Existing legacy narrative/semantic metric limitations are documented, not silently fixed under unchanged algorithm versions. New-family fixtures guard the new estimands.

### Frozen source-adapter details

- Vocabulary includes only `NamingStatus.ACTIVE` bindings with `merged_into is None`; candidates and retired bindings are excluded and counted separately. Hash the exact label token; do not substitute referents.
- Cultural feature inventory is retained ledger carriage; bounded eviction does not prove psychological forgetting. Local extinction is explicitly loss from the measured inventory population.
- Narrative ancestry is owner-qualified and only explicit lineage/parent/merge evidence is followed. Different owners' identical local IDs do not identify the same variant.
- Practical-knowledge continuity uses content keys and active entries; fidelity additionally needs comparable exact content fingerprints, attribution and donor state no later than acquisition.
- Group inputs are optional. The normal collector may supply detached existing analytical community outputs and region strata with explicit basis IDs; lack of those inputs is not a blocker for other metrics. Never invent authoritative groups to obtain a number.
- Within-group temporal deltas use identical owner pairs at both endpoints, not merely identical owner rosters. Both-empty-at-either-end pairs are excluded from both means with explicit counts.
- Requested baseline/end boundaries and capture policy/caps are part of evidence compatibility. Artifact decoding is duplicate-aware and bounded; filesystem readers/writers reject symlink escapes. Capture validation applies at initial skip, worker skip, sealed-archive adoption and fresh completion; requested artifact failures never authorize objective-history reruns.

### Summary comparison selection

Cross-run rows pool only population-summary measurements sharing scientific selectors, representations, units, denominator codes, exact requested/resolved windows, source revision and library-version compatibility. Match stable formula `measurement_id`, never unique `row_id`. Per-trait frequency and owner-local lineage detail remain within-run; there is no arbitrary cross-run trait alignment. Per-group inference requires an explicitly stable region/stratum selector; dynamic community labels alone are not compatible across runs. Uniformly represented fidelity is unavailable when source fingerprints encode incomparable provenance, not approximated from declared mutation flags. Default inference requires deterministic fake or validated immutable replay usage; other providers remain descriptive-only without that proof.

## Phase Index

1. [Phase 1: Observational evidence foundation](phase-01-evidence.md) — Tasks 1–3
2. [Phase 2: Population metrics](phase-02-population-metrics.md) — Tasks 4–6
3. [Phase 3: Specialized metrics](phase-03-specialized-metrics.md) — Tasks 7–9
4. [Phase 4: Integration and statistics](phase-04-integration-statistics.md) — Tasks 10–12
5. [Phase 5: Delivery](phase-05-delivery.md) — Tasks 13–15

## Cross-Phase Dependencies

- Task 2 depends on 1; Task 3 on 1–2 and owns canonical evidence serialization/digest construction.
- Tasks 4, 5 and 6 depend on 3.
- Task 7 depends on 3–4; Task 8 on 3 and 6; Task 9 on 3–4.
- Task 10 depends on 3–9, including Task 3's precomputed evidence digest; Task 11 on 2–3 and 10; Task 12 on 10–11. Task 10 must not depend on a codec deferred to Task 11.
- Task 13 depends on 11–12; Task 14 on 1–13; Task 15 on 14.
- Execute phases in listed order. Future parallelism is unnecessary; no agent/worktree concurrency is part of implementation.

## Tasks

### Phase 1: Evidence

- [x] Task 1: Define detached cultural evidence contracts ([details](phase-01-evidence.md#task-1-define-detached-cultural-evidence-contracts)).
- [x] Task 2: Capture finalized inventories without behavioral effects ([details](phase-01-evidence.md#task-2-capture-finalized-inventories-without-behavioral-effects)) (depends on 1).
- [x] Task 3: Normalize snapshots and attributable transmission evidence ([details](phase-01-evidence.md#task-3-normalize-snapshots-and-attributable-transmission-evidence)) (depends on 1, 2).

### Phase 2: Population metrics

- [x] Task 4: Implement frequency, persistence, extinction and diversity ([details](phase-02-population-metrics.md#task-4-implement-frequency-persistence-extinction-and-diversity)) (depends on 3).
- [x] Task 5: Implement mutation, fidelity and transmission classifications ([details](phase-02-population-metrics.md#task-5-implement-mutation-fidelity-and-transmission-classifications)) (depends on 3).
- [x] Task 6: Implement between-group divergence and within-group convergence ([details](phase-02-population-metrics.md#task-6-implement-between-group-divergence-and-within-group-convergence)) (depends on 3).

### Phase 3: Specialized metrics

- [x] Task 7: Implement baseline-cohort narrative persistence ([details](phase-03-specialized-metrics.md#task-7-implement-baseline-cohort-narrative-persistence)) (depends on 3, 4).
- [x] Task 8: Implement vocabulary inventory divergence ([details](phase-03-specialized-metrics.md#task-8-implement-vocabulary-inventory-divergence)) (depends on 3, 6).
- [x] Task 9: Implement technology retention and loss ([details](phase-03-specialized-metrics.md#task-9-implement-technology-retention-and-loss)) (depends on 3, 4).

### Phase 4: Integration and statistics

- [ ] Task 10: Register six versioned metric families ([details](phase-04-integration-statistics.md#task-10-register-six-versioned-metric-families)) (depends on 3, 4, 5, 6, 7, 8, 9).
- [ ] Task 11: Persist and propagate agent-level evidence artifacts ([details](phase-04-integration-statistics.md#task-11-persist-and-propagate-agent-level-evidence-artifacts)) (depends on 2, 3, 10).
- [ ] Task 12: Implement repeated-seed means, confidence intervals and paired contrasts ([details](phase-04-integration-statistics.md#task-12-implement-repeated-seed-means-confidence-intervals-and-paired-contrasts)) (depends on 10, 11).

### Phase 5: Delivery

- [ ] Task 13: Expose opt-in capture and comparisons through the matrix CLI ([details](phase-05-delivery.md#task-13-expose-opt-in-capture-and-comparisons-through-the-matrix-cli)) (depends on 11, 12).
- [ ] Task 14: Add hand-calculated and real-scenario end-to-end gates ([details](phase-05-delivery.md#task-14-add-hand-calculated-and-real-scenario-end-to-end-gates)) (depends on 1–13).
- [ ] Task 15: Complete mandatory documentation and implementation handoff ([details](phase-05-delivery.md#task-15-complete-mandatory-documentation-and-implementation-handoff)) (depends on 14).

## Commit Plan

Suggested checkpoints only; never commit without user authorization.

- Commit 1, Tasks 1–3: `feat(analysis): capture owner-scoped cultural evolution evidence`
- Commit 2, Tasks 4–6: `feat(analysis): measure cultural trait dynamics and transmission`
- Commit 3, Tasks 7–9: `feat(analysis): measure narrative vocabulary and technology continuity`
- Commit 4, Tasks 10–12: `feat(experiments): add cultural metric artifacts and seed-block confidence intervals`
- Commit 5, Tasks 13–15: `feat(research): expose and document cultural evolution comparisons`

## Definition of Done

- Every requested metric area has a distinct applicable estimand, formula/denominator, missing-data policy and owner-level evidence trail; unavailable evidence never becomes invented culture or perfect fidelity.
- Six new families validate at catalog count 136, without changing old family algorithms or default outputs.
- Full captured inventory history supports measurable persistence/loss; gaps, bounded exports, dynamic populations and ancestry uncertainty remain explicit.
- Confidence intervals are genuine repeated-seed mean/paired-difference intervals with effective independent n and assumptions; legacy percentile ranges remain descriptive ranges.
- Real BM-derived execution reaches stored evidence, metrics and standalone paired summary; hand-calculated fixture covers all 14 areas without requiring scripted cultural emergence.
- V1 gate, V2 scientific invariants, architecture/import checks, type checking, Ruff and coverage-enabled tests pass. No secrets/payloads appear in logs or default presentation/API surfaces.
- Mandatory documentation checkpoint explains scientific limitations and resume/capture compatibility. No new world/cognitive authority, capability flag or runtime schema is introduced.
- Window selection, fixed-pair denominators, actual stream alignment and all four matrix completion paths have concrete regression evidence, including real recovery and artifact fault injection.

## Refinement History

2026-10-23 — `$aif-improve`, all eight findings approved by the user. Preserved 15 task IDs, five phases, settings and Original Request. Added explicit channel/failure coverage; recovery-safe publication; exact selectable analysis windows; fixed-pair convergence; complete measurement contracts and early evidence codec/digest; all-path completion/artifact failure rules; actual random-channel identity and rematerialized one-factor comparisons; duplicate-aware, bounded, symlink-safe artifact I/O. Corrected Task 10's evidence-codec ordering by assigning that foundation to Task 3. No implementation work or requirement-source edits were performed.

## Open Questions and Limits

No blocking architectural question remains. Applicability is evidence-dependent: some real runs lack attributable donor pairs, complete archive coverage or stable group alignment. These yield explicit unknown/excluded measurements, not implementation guesses. CI interpretation assumes distinct selected seeds represent independent simulation draws and approximately well-behaved seed-block means; n and assumptions are always reported. Multiple-testing correction, hypothesis testing, bootstrap methods, fuzzy trait ontologies, automatic cross-run community alignment, durable subjective restart and unrelated legacy metric repairs are outside this plan.

## Execution Handoff

Start with `$aif-implement .ai-factory/plans/v3-37-cultural-metrics/index.md`. Read this manifest plus the complete current phase before implementing a task. Only this file owns task progress; phase files contain no task checkboxes. Revalidate current source symbols before edits, preserve user changes, and load directory-scoped instructions for any newly touched path. Do not infer that the roadmap's historical counts are current contracts.
