# Analysis Metrics (V1 Specifications)

[← Experiments](experiments.md) · [Memory reconstruction](memory-reconstruction.md) · [Back to README](../README.md)

Executable formula, population, and edge-case policy for all nineteen metric families lives in `analysis.specifications`. Implementations must consume these specs; they do not redefine denominators ad hoc.

## Catalog

| Family | Version ID | Evidence stages (primary) |
| --- | --- | --- |
| `resource_inequality` | `resource_inequality@1` | objective event/state |
| `cooperation` | `cooperation@1` | objective events + action resolution |
| `conflict` | `conflict@1` | objective events + action resolution |
| `survival` | `survival@1` | objective event/state |
| `goal_completion` | `goal_completion@1` | goal transitions |
| `repeated_conventions` | `repeated_conventions@1` | objective events + action resolution |
| `behavioral_specialization` | `behavioral_specialization@1` | objective events + action resolution |
| `memory_drift` | `memory_drift@1` | agent-visible + memory stages |
| `memory_dynamics` | `memory_dynamics@1` | V2 recall audits (reconstruction stage) |
| `offline_consolidation` | `offline_consolidation@1` | harvested sleep-consolidation audits |
| `reflection` | `reflection@1` | harvested reflection audits |
| `identity_dynamics` | `identity_dynamics@1` | identity audit (belief-revision testimony stage) |
| `belief_accuracy` | `belief_accuracy@1` | belief revision (ClaimTruthSpec only) |
| `false_belief_persistence` | `false_belief_persistence@1` | belief revision + truth specs |
| `relationship_stability` | `relationship_stability@1` | relationship revisions |
| `trust_network_structure` | `trust_network_structure@1` | relationships (+ optional interactions) |
| `group_community_structure` | `group_community_structure@1` | nonnegative trust projection |
| `knowledge_diffusion` | `knowledge_diffusion@1` | delivery / traces / beliefs / reconstruction |
| `rumor_distortion` | `rumor_distortion@1` | multi-hop structured content |
| `counterfactual_reasoning` | `counterfactual_reasoning@1` | harvested counterfactual audits plus committed event ids |
| `territorial_concentration` | `territorial_concentration@1` | detached presence / control spatial rows |
| `prediction_calibration` | `prediction_calibration@1` | joined confidence / empirical outcome rows |
| `belief_convergence` | `belief_convergence@1` | detached belief claim rows |
| `cultural_similarity` | `cultural_similarity@1` | naming / norms / conventions / narratives rows |
| `kinship_genealogy` | `kinship_genealogy@1` | detached kinship edge rows |
| `dependency_survival` | `dependency_survival@1` | detached dependency agent / survival rows |
| `caregiver_diversity` | `caregiver_diversity@1` | detached care-act rows |
| `caregiving_burden` | `caregiving_burden@1` | detached care-act rows |
| `intergenerational_cooperation` | `intergenerational_cooperation@1` | detached care-act + kinship rows |

Catalog version: `metric-catalog-v1`. Document schema: `MetricDocument` schema `1`. Closed catalog cardinality: **103** families (`METRIC_FAMILY_COUNT`). New opt-in families assemble only when their detached inputs are present.

### Additive analysis surfaces (off the V1 gate)

- **Trust centrality keys** on `trust_network_structure@1`: `centralization_out`, `mean_degree_centrality`, `mean_betweenness_centrality`, `mean_closeness_centrality` (exact NetworkX on nonnegative projection; `n<2` stays unknown).
- **Reputation distributional keys** on `distributed_reputation@1`: `neighborhood_count`, `mean_pairwise_gap`, `max_pairwise_gap` (absent when `<2` neighborhoods). Legacy `*_gap` keys stay bit-identical.
- **Survival cohort contrast** sibling document (`survival_cohort_contrast@1`) — not a catalog family. Missing cohort map omits the sibling; `survival@1` fingerprints stay unchanged.
- **Phenomenon indicator panel** (`phenomenon-indicators-v1`): multi-indicator `support_band` codes `absent` / `weak` / `moderate` / `strong`. Forbidden: `culture_emerged`, `norm_emerged`, `society_formed`, `emerged`, `detected`.
- **Matrix metric summary** (`matrix-metric-summary-v1`): percentile distribution + CI summaries over optional `cells/<cell_id>.metrics.json` sidecars. Sibling to ref-only `matrix-aggregate-v1`.

`memory_dynamics@1` values: `recall_accuracy`, `source_confusion`, `memory_survival`, `interference`, `confidence_calibration`. Assembled only when `MetricComputationInputs.memory_dynamics_report` is present (in-run V2 audit export). REFERENCE / V1 reconstructive arms leave the family absent.

`offline_consolidation@1` values: `consolidation_invocations`, `traces_strengthened`, `traces_soft_forgotten`, `patterns_merged`, `belief_revisions`, `relationship_revisions`, `goal_transitions`. Assembled only when `offline_consolidation_report` is present. A missing report does not change V1 catalog assembly. Assembly logs `offline_consolidation_metrics_assembled` with the family id and value keys only.

`reflection@1` values: `reflection_invocations`, `belief_revisions`, `hypotheses`, `goals_adopted`, `goals_abandoned`, `relationship_reassessments`, `patterns_detected`. Assembled only when `reflection_report` is present. Disabled arms and missing reports stay absent and do not change V1 catalog assembly. Assembly logs `reflection_metrics_assembled` with the family id and which value keys are present. Belief text and memory content are not logged.

`identity_dynamics@1` values: `aspect_*` counts for the eleven identity topics, `stability_low` / `stability_mid` / `stability_high`, dissonance counts for `commitment_command`, `inferred_value_command`, and `risk_above_tolerance`, and `owner_divergence`. A missing audit or a flags-off run with no qualifying heads is absent, not zeros. The mapper logs `identity_dynamics_mapped` with schema version, owner count, and present/absent. It does not store claim text. Live cognition does not read the report.

`counterfactual_reasoning@1` values: `scenario_count` and `event_overlap_count`. The family is present only when a counterfactual audit exists; a disabled run with an empty audit tuple stays absent. It compares harvested audit counts with committed event ids after the run and reports that no scenario id equals a world event id when the overlap is zero. Assembly logs `counterfactual_metric` with the arm id, scenario count, and overlap count. It does not log scenario payloads. `runner-config-v8` is the counterfactual schema and may also carry consolidation, reflection, and prospective imagination. The document is not an input to the cognitive loop.

`cultural_narrative_lineage@1` values: `active_variant_count`, `mean_active_strength`, `mean_duration_ticks`, `persistence_rate`, `branch_rate`, `mean_mutation_generation`, `fingerprint_churn`, `token_add_rate`, `token_loss_rate`, `inaccuracy_vs_objective`, `source_event_drop_rate`, `origin_shift_rate`, `orphan_retell_rate`, `merge_rate`, `mean_parents_per_merge`, `competing_variant_share`, `mean_location_span`, `mean_carrier_span`, `multi_location_rate`, `social_reach_rate`. Computed from caller-supplied detached variant history rows after the run. Empty denominators are absent for that key only. Experiment AB stays off the V1 gate. The document is not an input to cognition.

### Dependency / caregiving families (off the V1 gate)

`dependency_survival@1`, `caregiver_diversity@1`, `caregiving_burden@1`, and `intergenerational_cooperation@1` assemble only from detached post-run rows (`analysis.dependency_care_metrics`). They never invent caregiver roles from kinship alone, never feed cognition, and stay absent when dependency-care inputs are missing. Experiment AI stays off the V1 gate.

### Developmental learning families (off the V1 gate)

`developmental_acquisition@1`, `developmental_source_mix@1`, and `developmental_divergence@1` assemble from harvested `DevelopmentalAcquisitionAudit` rows and/or owner `DevelopmentalKnowledgeLedger` snapshots (`analysis.developmental_learning_metrics`). They never overload `knowledge_diffusion` / `cultural_transmission`, never include concept payloads, and never feed cognition. Experiment AJ stays off the V1 gate.

### Mentorship families (off the V1 gate)

`mentorship_fidelity@1`, `mentorship_mutation@1`, and `mentorship_bonds@1` assemble from harvested `MentorshipAudit` rows and optional owner `MentorshipLedger` snapshots (`analysis.mentorship_metrics`). They never overload `cultural_transmission@1`, never include content fingerprints as payloads, and never feed cognition. Experiment AK stays off the V1 gate.

### Cultural feature provenance families (off the V1 gate)

`cultural_feature_provenance@1`, `cultural_trait_diffusion@1`, and `cultural_feature_mutation@1` assemble from harvested `CulturalFeatureAudit` rows and optional `AnalyticalCulturalTrait` clusters (`analysis.cultural_feature_metrics` / `analysis.cultural_traits`). They never overload V2 Experiment S / `cultural_transmission@1`, never promote analytical traits into agent stores, and never feed live cognition. Experiment AL stays off the V1 gate.

### Historical memory layer families (off the V1 gate)

`historical_memory_layers@1`, `historical_memory_transitions@1`, and `historical_memory_queries@1` assemble from analysis-only Assmann layer harvests (`analysis.historical_memory` / `analysis.historical_memory_metrics`) when `HistoricalMemoryLayersSpec` is present on `runner-config-v32` (or optional layers on `v33`). Layer histograms, transition counts, and the locked researcher query report (`any_direct_witnesses_alive`, `anyone_remembers_speaking_to_witness`, `event_known_only_from_stories_or_artifacts`) are researcher constructs only. They never write layer labels into Observation, SelfModel, or subjective ledgers, never overload cultural-feature or narrative families, and never feed cognition. Experiment AM stays off the V1 gate.

`durable_record_lineage@1`, `durable_record_fidelity@1`, and `durable_record_survival@1` assemble from duck-typed durable harvest rows when `DurableRecordsSpec` is present on `runner-config-v33|v34` (deepens owned `cultural_historical_memory`; no new V3 flag). Signals are copy-tree depth / generation histograms, perfect-vs-mutated-vs-lossy rates with mark/relation edit distances, and integrity / author-death / false-record persistence counts — never mark payloads, never cognition feed, and never overloads of `external_artifact_memory@1` or historical-memory families. Experiment AN stays off the V1 gate.

`knowledge_repository_survival@1`, `knowledge_repository_access@1`, and `knowledge_repository_organization@1` assemble from duck-typed repository harvest rows when `KnowledgeRepositoriesSpec` is present on `runner-config-v34|v35` (deepens the same cultural flag; requires durable + provenance; no new V3 flag). DTOs are counts/histograms only (`RepositorySurvivalSummary`, `RepositoryAccessSummary`, `RepositoryOrganizationSummary`) — repository/status/membership/access/index history as ids and ticks, never mark payloads or cultural archive/library labels, never cognition feed, and never overloads of durable-record or historical-memory families. Experiment AO stays off the V1 gate.

### Knowledge genealogy families (off the V1 gate)

`knowledge_genealogy_holders@1`, `knowledge_genealogy_lineage@1`, and `knowledge_genealogy_mutation@1` assemble from harvested `PracticalKnowledgeAudit` rows when `KnowledgeGenealogySpec` is present on `runner-config-v35` (deepens owned `cultural_historical_memory`; no new V3 flag; no write-pair). DTOs are counts/histograms only — living vs dead holders (via `death_ticks`), root/multi-parent/combination rates, mutated-hop share and mean `fingerprint_distance_q`, origin histogram — never technique payloads, never cognition feed, and never overloads of `skill_learning@1`, mentorship, cultural-feature, durable-record, or repository families. Analysis-only `KnowledgeGenealogyGraph` supports the four locked researcher queries (`who_currently_knows`, `who_taught`, `oldest_surviving_lineage_origin`, `independent_emergence_count`); cross-owner `transmitted_from` edges are analysis joins only. Experiment AP stays off the V1 gate.

### Bounded experiment families (off the V1 gate)

`bounded_experiment_trials@1`, `bounded_experiment_discovery@1`, and `bounded_experiment_provenance@1` assemble from detached trial audits and practical-knowledge evidence refs when `BoundedExperimentationSpec` was present on `runner-config-v36`. They deepen owned `cultural_historical_memory` and do not overload genealogy, skill, cultural, durable, or repository families. Documents are counts and shares only: outcome and operator histograms, deliberate versus accidental counts, unexpected share, and the share of learned entries that cite `evt:{id}` from a harvested trial. That provenance share is zero when genealogy uptake is off. `knowledge_provenance_for_experiment(event_id)` returns holder entry ids that cite the event, or an empty tuple. Analysis does not import cognition ledgers or the private law catalog. Experiment AQ stays off the V1 gate.

### Technique lifecycle families (off the V1 gate)

`technique_lifecycle_state@1`, `technique_lifecycle_loss@1`, and `technique_lifecycle_diffusion@1` assemble only when `TechniqueLifecycleSpec` is present on `runner-config-v37`. They label existing practical-knowledge keys as discovered, known, diffusing, rare, locally extinct, globally lost, or rediscovered, and they attach loss causes (`holders_died`, `records_destroyed`, `materials_absent`, `teaching_chain_failed`). `technique_lineage_diffusion(content_key, as_of_tick)` returns counts and lineage root ids. These rows are research inferences. They are not agent-visible facts, and an empty harvest when the channel is off is absence, not a measured extinction. Experiment AR stays off the V1 gate.

### Possession succession families (off the V1 gate)

`possession_custody_outcomes@1`, `possession_claim_conflict@1`, and `inheritance_convention_distribution@1` assemble only when `possession_succession` is present. They read corpse-custody episodes. A holder is physical possession. A doctrine is a legitimacy claim. Ties are `contested`. No living support at the death location is `unformed`. A missing kinship, care, or group harvest is `not_applicable` for that doctrine, not a false heir. A parent edge does not count as a caregiver. The convention token is not written back into any ledger. An empty harvest when the channel is off is absence. Experiment AS stays off the V1 gate. Research UI badges for these three ids are `research_inference` and do not name a legal owner.

### Structured commitment families (off the V1 gate)

`commitment_term_divergence@1`, `commitment_fulfillment_status@1`, and `commitment_social_consequences@1` assemble only when `structured_commitments` is present. They read speech tokens and each owner's stored terms. A missing row is `unformed`. Disagreement is `divergent`. A status histogram is not a world fact. A later `Given` is an item move, not a verdict. Consequence counts are requests, not health or inventory changes. `world_enforcement` stays false and `institution` stays `none`. An empty harvest when the channel is off is absence. Experiment AT stays off the V1 gate. Research UI badges for these three ids are `research_inference` and do not name a legal debt.

### Subjective valuation families (off the V1 gate)

`exchange_reservation_divergence@1`, `exchange_negotiation_path@1`, and `exchange_realized_bundles@1` assemble only when `subjective_valuation` is present. A reservation is that owner's private belief. A missing ledger is `unformed`. Two different tool reservations are `divergent`. The path counts offers, counteroffers, withdrawals, and completions. A withdrawn offer is not a transfer. `realized_bundle` stores kind counts from a completed swap, such as three food and one tool. Those counts are the items that changed hands. `institution` stays `none`. An empty harvest when the channel is off is absence. Experiment AU (`subjective_exchange@1`) stays off the V1 gate. Research UI badges for these three ids are `research_inference`. Badge copy says reservation or bundle.

### Exchange-function families (off the V1 gate)

`exchange_acceptance_share@1`, `exchange_acquisition_fate@1`, and `exchange_quote_homogeneity@1` assemble only when `resource_exchange_profile` is present. They count completed swaps, later transfers of an acquired item, and offers whose one side is homogeneous in a kind. A missing acceptance row is not a count of zero stock. Numerators and denominators are integers, or null when the denominator is zero. No row names a kind as money. Experiment AV (`exchange_functions@1`) stays off the V1 gate. Research UI badges say acceptance share, acquisition fate, or quote homogeneity.

### Collective-project families (off the V1 gate)

`collective_project_progress@1`, `collective_project_contribution@1`, and `collective_project_outcome@1` assemble only when `collective_projects` is present. Progress sums labor and materials by kind. Contribution counts distinct accepted actors, accepted attempts, and shortages. Outcome counts completed, abandoned, and still-open sites. Numerators and denominators are integers. No row names a crew or a leader. An empty harvest when the channel is off is absence. Experiment AW (`collective_projects@1`) stays off the V1 gate.

### Public-good families (off the V1 gate)

`public_good_contribution_inequality@1`, `public_good_benefit_distribution@1`, `public_good_maintenance_burden@1`, `public_good_free_rider_pattern@1`, and `public_good_cooperation_stability@1` assemble only when `public_goods` is present. They fold objective project and public-act events into contribution Gini, per-kind benefit counts, integrity burden, co-occurrence patterns, and quiet-gap counts. `public_good_free_rider_pattern` is a co-occurrence count only: it does not assign a role or emit a boolean. A benefit event is neither an access grant nor a moral classification. Channel off writes no rows. Experiment AX (`public_goods@1`) stays off the V1 gate.

### Supporting formulas (not a separate family)

`action_resolution_rates@1` defines attempted / applied / rejected / conflicted rates **only** from `ActionResolution` evidence. Never infer rejected attempts from absent world events. Task 11 implementations reuse this shared spec beside cooperation/conflict occurrence rates.

## Shared policies

- **Numerical:** `analysis.numerical` — float64 intermediates, sort-before-reduce, banker's quantization to 12 decimal places, signed-zero normalization, canonical quantized output (not BLAS bit-identity).
- **pandas:** `NA` is unknown; never coerce to zero; sort keys; stable mergesort ties.
- **SciPy:** empty/single-sample distributions → `unknown`; never coerce empty entropy/divergence to zero.
- **NetworkX:** lexicographic node order; community algorithm `networkx.community.greedy_modularity_communities` on a nonnegative projection with deterministic tie-break.
- **Availability:** missing or unobservable evidence is `unknown`, never silent zero/false.
- **Deceased agents:** excluded from living opportunity denominators; survival and goal death outcomes use objective death evidence; post-death no-action ticks are expected.
- **Self-edges:** relationship self-targets forbidden; graph self-loops dropped; self-communication counted separately from dyadic cooperation.
- **Action vocabulary (V1):** move, search, take, drop, give, eat, drink, sleep, talk, ask, tell, help, attack, flee, wait. Cooperation and conflict kinds stay disjoint. Dependency-care analysis also counts `feed` / `transport` in `COOPERATION_ACTION_KINDS` when those occurrences are present (channel-on only; never inputs to cognition).
- **Motifs:** contiguous n-grams (n∈{2,3}), optional explicit gap policy, `min_support=2`, sorted by `(-support, motif_id)`. No culture/role labels.
- **Adoption stages:** `world_delivery`, `receiver_trace`, `belief_candidate`, `belief_activation`, `reconstruction`, `retell`. Prefer explicit transmission roots; never invent parents from hop order.
- **Evidence-stage dedup:** corroboration by lineage root within a stage; never collapse stages into one narrative class.
- **Signed trust:** values in `[-1, 1]`; community detection uses `w = max(trust, 0)` only.
- **Resource measures:** inventory count/load, extraction, transfer, consumption-access — never labeled “wealth”.
- **Belief accuracy:** only claims covered by analysis-only `ClaimTruthSpec`; unevaluable claims stay out of the denominator.

## Empty / one / all-zero / unknown

Each `MetricSpecification` records explicit `empty_case`, `one_case`, `all_zero_case`, and `unknown_case` strings. Known-answer coverage lives in `tests/unit/metric_fixtures.py` (reference-scenario-shaped cases plus small degenerates).

## API surface

```python
from analysis import (
    MetricFamilyId,
    all_metric_specifications,
    metric_specification,
    validate_metric_catalog,
    action_resolution_rate_spec,
)

validate_metric_catalog()
spec = metric_specification("resource_inequality")
print(spec.version_identifier, spec.formulas["gini"])
```

Validation errors expose only `metric_family`, `algorithm_version`, and a stable `reason_code`.

## Logging

Specification and model code is log-free. Metric implementations emit DEBUG metadata (family, version, counts, duration) without evidence payloads.

## Tests

```bash
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_metric_specifications.py \
  tests/unit/test_metric_properties.py \
  tests/unit/test_metric_determinism.py \
  tests/unit/test_metric_service.py \
  tests/unit/test_reference_scenario_e2e.py -q
```

## Multiple-societies families (off the V1 gate)

These families are analysis-only candidate labels. No society, community, or
polity entity exists in the world, agents, or persistence.

| Family | Version ID | Evidence stages (primary) |
| --- | --- | --- |
| `society_emergence` | `society_emergence@1` | living-person residence / interaction / trust lanes |
| `society_divergence` | `society_divergence@1` | detached digest distributions per dimension |
| `society_isolation` | `society_isolation@1` | cross-community evidence edges + arrival ticks |

- `society_emergence@1` clusters the union graph with the same recorded
  `networkx.community.greedy_modularity_communities` entry used by group
  community metrics. Zero-edge persons remain explicit singletons; dead persons
  are excluded. Community ids are SHA-256 derived from sorted person ids.
- `society_divergence@1` computes symmetric pair-scoped and
  community-vs-global-baseline Jensen–Shannon divergence for vocabulary, norms,
  conventions, technology, stories, institutions, and trade. A missing channel
  is `absent` for that dimension, never zero. The shared comparator lives in
  `analysis.numerical.jensen_shannon_divergence`.
- `society_isolation@1` classifies each cross-community evidence edge as
  `journey_explained` when a completed arrival between the communities precedes
  the edge's logical tick, or `unexplained` otherwise. Counts, coverage, and
  reason codes are reported; nothing is auto-fixed.


## Cultural contact families (`society_contact` through `contact_reputation_transfer`)

Six analysis-only families connect separately developed candidate communities after a
neutral cross-region co-presence fact:

| Family | What it reports | Availability rule |
| --- | --- | --- |
| `society_contact@1` | Pair onset, contact/location-tick counts, cross-community person-ticks, dyadic communication/exchange/teaching/cooperation/conflict, cross-community kinship edges | Absent without a cross-community pair |
| `contact_cultural_change@1` | Exact pre (`tick < onset`) and post (`onset <= tick <= final`) Jensen-Shannon divergence per dimension using one shared token universe per pair/dimension; convergence delta, converging/continued-divergence counts, membership stability | Partial/absent when either window or channel is missing |
| `contact_hybrid_practice@1` | Cross-community combinations, recombined cultural beliefs, shared narrative roots, naming merges, hybridization rate, unresolved lineage | Absent without resolvable lineage |
| `contact_knowledge_transfer@1` | Practical-knowledge transfers by channel (`teaching`, `imitation`, `written_record`, `reconstruction`, `combination`), donor→recipient pairs, mean hop, mutated transfers | Absent without a transfer channel |
| `contact_lexical_borrowing@1` | Communicated cross-community label evidence, new adoption vs reinforcement, binding strength, unresolved actors | Absent without communicated naming evidence |
| `contact_reputation_transfer@1` | Only `communication` / `third_party_story` cross-community evidence with `source != target`; direct observation and remembered interaction are coverage, not transfer | Absent without a reputation channel |

Contact is descriptive, not causal or normative: convergence and continued
divergence are both valid outcomes, and no threshold defines successful
assimilation, multiculturalism, war, or cooperation. Direct/remembered
reputation evidence is first-hand and is never counted as transfer.
`ProjectContributed` and `PublicGoodMaintained` are collective coverage, not
dyadic contact cooperation. Intermarriage is unsupported; cross-community
kinship is reported only from objective parent→child edges.
