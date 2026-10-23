# Phase 2: Trait dynamics, transmission and population structure

Plan: [index.md](index.md)  
Tasks: 4–6  
Depends on: Tasks 1–3

## Objective

Compute separate cultural measurements with auditable populations, denominators and censoring. No overall culture index is introduced.

## Current-Code Evidence

| Path | Symbols | Why it matters |
|---|---|---|
| `src/analysis/cultural_traits.py` | `compute_analytical_cultural_traits` | Accumulated audit carrier counts are not point prevalence. |
| `src/analysis/cultural_feature_metrics.py` | `compute_cultural_feature_mutation`, `compute_cultural_trait_diffusion` | Preserve historical occurrence formulas unchanged. |
| `src/analysis/cultural_similarity_metrics.py` | `compute_cultural_similarity` | Per-channel Jaccard precedent, not a global culture score. |
| `src/analysis/numerical.py` | `jensen_shannon_divergence`, `quantize_float` | Existing finite/empty/numerical conventions. |
| `src/analysis/society_divergence.py` | `SocietyDigestRow`, `compute_society_divergence` | Detached community/dimension measurements already exist. |

## Files to Change

Create `src/analysis/cultural_trait_dynamics.py`, `src/analysis/cultural_evolution_transmission.py`, `src/analysis/cultural_population_structure.py` and matching `tests/unit/test_cultural_trait_dynamics.py`, `test_cultural_evolution_transmission.py`, `test_cultural_population_structure.py`.

## Task 4: Implement frequency, persistence, extinction and diversity

### Intent

Distinguish prevalence, continuity and loss, using inventory state rather than occurrence totals.

### Implementation Steps

1. Add `compute_cultural_trait_dynamics(inputs) -> tuple[CulturalMeasurement, ...]`. For every feature kind, boundary and requested population stratum, count each living owner once per exact trait digest. Frequency is carriers / all living owners whose channel is enabled; record observed/expected owner coverage. Disabled owners are excluded from the channel population, not counted as culturally empty.
2. Publish exact population prevalence only when every eligible owner inventory and the living roster are complete. Under partial coverage publish observed counts/coverage and null population prevalence; do not quietly change the denominator. A complete roster with eligible owners but no entries is a known zero frequency for previously observed traits.
3. A baseline trait cohort is the distinct set present at the exact `CulturalAnalysisWindow.baseline_boundary`. Do not shift to the first complete or nonempty boundary. Endpoint persistence is baseline traits present at the exact resolved end / baseline traits. A complete empty baseline gives baseline count 0 and null persistence (`empty_baseline`); a missing baseline gives unknown coverage, not count 0. Continuous persistence additionally requires presence at every intervening complete boundary. Report both with fixed baseline denominators, not survivors-only denominators. Missing intermediate frames censor continuous persistence even when endpoint presence is known. Frequencies/diversity at independently complete boundaries can still compute even when a cohort estimand is unavailable.
4. Extinction is a transition from positive prevalence to zero at the next complete boundary, limited to the declared living-carriage population. Record last-positive and first-zero boundaries. Local extinction uses fixed group membership. No eligible living owners yields `population_empty`, not proof of trait extinction. Reappearance after zero is a new presence episode; it is not rediscovery without explicit provenance.
5. Compute richness `S`, Shannon entropy `-sum(p_i ln p_i)`, effective diversity `exp(H)` and Simpson diversity `1-sum(p_i^2)` separately by feature kind/boundary/group. Here `p_i` is carrier incidences for trait i divided by all trait-carrier incidences, not population prevalence. Deduplicate owner/trait pairs before summing. Record incidence count and carrying-owner count.
6. For complete, nonempty eligible populations with no traits: richness/entropy/Simpson/effective diversity are 0 by declared empty-inventory convention. A singleton trait has H=0, effective diversity=1 and Simpson=0. Missing populations or inventories yield nulls, not these zeros.

### Required Interfaces and Contracts

New family `cultural_trait_dynamics@1`. Measurements include `trait_frequency`, `endpoint_persistence`, `continuous_persistence`, `extinction_transition`, `richness`, `shannon_entropy`, `effective_diversity`, `simpson_diversity`. No cross-kind average. Persist baseline/endpoint identities, episode boundaries, counts, exclusions and evidence refs. No Kaplan–Meier/extrapolated lifetime claims in v1; durations are observed lower bounds with left/right-censor flags.

### Requirement Evidence

User: trait frequency/persistence/extinction/diversity; existing audit formulas are occurrence-based, so this is a new family rather than a silent algorithm change. Test complete, partial, empty and gap combinations from the index.

### Error Handling and Logging

Invalid windows/populations fail with safe codes. Missing frames censor results; no forward filling. DEBUG logs counts by dimension, not tokens or values.

### Tests

Hand-calculated three-owner/two-trait fixture; duplicate beliefs per owner; birth and death changing denominators; baseline A disappears while unrelated B survives; disappearing/reappearing A; exact nonzero baseline after initial empty inventories; missing requested baseline does not shift; requested end later than an early stop; empty versus missing baseline; gap before zero; no eligible owners; disabled owner; bounded-ledger disappearance; uniform and singleton diversity. Hypothesis: frequency in [0,1], diversity invariant to input order and owner renaming.

### Acceptance Criteria and Verification

Known counts and all formulas match hand calculations; incomplete coverage never becomes exact prevalence/extinction. Run `uv run pytest tests/unit/test_cultural_trait_dynamics.py --cov=analysis --cov-report=term`.

## Task 5: Implement mutation, fidelity and transmission classifications

### Intent

Measure what changed on evidenced acquisition edges without confusing delivery, genealogy or modality.

### Implementation Steps

1. Add `compute_cultural_evolution_transmission(inputs)`. Enumerate deduplicated acquisition candidates and retain classified, unclassified and ambiguous counts for every feature kind/modality.
2. An exact-fidelity opportunity requires a resolved donor state and comparable canonical source/recipient fingerprints of the same representation. `exact_fidelity = equal_digest_edges / comparable_single_source_edges`. Differences measure representational change, not misinformation. Never compare fingerprints that intentionally encode different speaker/source identities; classify those as `representation_not_comparable` unless an existing source contract supplies a shared content projection.
3. `mutation_rate = changed_edges / comparable_single_source_edges`; report existing declared mutation flags separately as `declared_mutation_share` over candidates carrying that flag. Do not equate an absent mutation flag with perfect fidelity. Multi-parent recombination has its own count/share and is excluded from the single-source mutation/fidelity denominator.
4. Report horizontal, forward-intergenerational, reverse-intergenerational and unknown counts. Shares use attributable edges with known generation class; expose that denominator and the unknown count. `vertical_kin_share` is the explicit parent→child subset, not a synonym for all intergenerational transfers.
5. Give independent rediscovery, artifact acquisition, self-revision, reinforcement and unresolved testimony their own counts. They do not create successful social transmission edges. Preserve edge-level evidence IDs and acquisition boundaries in detail rows.

### Required Interfaces and Contracts

New family `cultural_evolution_transmission@1`; no cognitive-policy or audit-format change. If no applicable comparable edge exists, fidelity/mutation are null even when acquisition counts are present. Genuine comparable zero changes yields mutation 0, not absent. Channel and generation are independent selectors.

### Requirement Evidence

User: mutation/fidelity/horizontal/vertical transmission and provenance; architecture: testimony proves neither truth nor independent corroboration. Expected combinations include verified same-generation teacher, older unrelated teacher, actual parent, artifact with unknown donor and independent rediscovery.

### Error Handling and Logging

Reject structurally contradictory edge IDs. Preserve unresolved attribution as exclusions. Metadata-only DEBUG count summaries; no edge fingerprints or communication bodies in logs.

### Tests

Exact copy, changed copy, recombination, repeated reinforcement, ambiguous donor, later donor revision, declared mutation disagreeing with exact evidence, parent versus unrelated teacher, reverse-generation transfer, missing generation and representation mismatch. Assert numerator <= denominator, stable input ordering and zero-opportunity nulls.

### Acceptance Criteria and Verification

Rates use eligible edges only and every counted transfer resolves to agent-level provenance. Run `uv run pytest tests/unit/test_cultural_evolution_transmission.py tests/unit/test_cultural_feature_metrics.py --cov=analysis --cov-report=term`; legacy formulas remain unchanged.

## Task 6: Implement between-group divergence and within-group convergence

### Intent

Keep group comparisons dimensional, observational and membership-aware.

### Implementation Steps

1. Add `compute_cultural_population_structure(inputs)`. Use explicit boundary-scoped detached group memberships; never infer membership from trait similarity inside this metric. Accept at most one group per owner per partition/boundary; independent partitions have different basis IDs.
2. Construct carrier-incidence distributions on the sorted union of trait digests separately for each feature kind. Compute pairwise group JS divergence using existing `analysis.numerical.jensen_shannon_divergence`; retain its existing natural-log units and document the bound ln(2), not [0,1]. Null if either distribution has no mass.
3. For a point-in-time group measurement, enumerate unordered pairs of distinct completely observed living owners. Both-empty pairs are excluded with explicit counts; empty/nonempty distance is 1; nonempty/nonempty distance is `1-|A∩B|/|A∪B|`. No eligible pair is null, not zero. Do not treat missing inventories as empty.
4. Longitudinal within-group convergence uses a fixed owner cohort AND a fixed pair set. First choose owners living, fully observed and in the same group/partition at both exact requested endpoints. Enumerate their unordered pairs once, and keep a pair only if its inventory union is nonempty at BOTH endpoints. Compute both endpoint means over that identical pair set, then subtract endpoint mean from baseline mean. Publish eligible pair IDs/count, excluded both-empty-at-baseline/end counts, cohort size and excluded entrants/exits/deaths. If the pair set is empty, convergence is null. Positive means convergence, negative divergence; neither membership churn nor endpoint-specific pair dropout is cultural adaptation. Persist both pair inventories as provenance for the denominator.
5. Between-group change uses corresponding fixed cohorts for each side. Stable explicit group IDs are required; detached dynamically inferred communities without evidenced identity alignment receive point-in-time divergence only. Region strata may be supplied with basis `region`, but are never labeled societies or polities.

### Required Interfaces and Contracts

New family `cultural_population_structure@1`; dimensions remain separate. Empty/missing group input means unavailable group metrics, not global zero divergence. Global trait dynamics still compute without groups. All pair and cohort rows carry membership evidence as well as trait evidence.

### Requirement Evidence

User: between-group divergence/within-group convergence; architecture: analytical classifications cannot become world institutions. Compatibility: reuse numerical helper without silently rescaling legacy metrics.

### Error Handling and Logging

Overlapping membership within a partition fails `ambiguous_group_membership`. Unaligned longitudinal groups produce null with `group_identity_unaligned`. Log group/pair/exclusion counts only.

### Tests

Identical/disjoint/partially overlapping distributions; JS symmetry; empty mass; singleton group; empty inventories; actual convergence; stable cultures with only migrants changing composition; group split/merge without alignment. Include a three-owner case where one pair becomes both-empty and separately computed endpoint pair sets would reverse the sign; require identical pair IDs/counts and the hand-calculated fixed-pair delta. All pairs excluded yields null convergence. Hypothesis input permutation and JS bounds.

### Acceptance Criteria and Verification

No membership churn is mistaken for convergence and no cross-dimension score exists. Run `uv run pytest tests/unit/test_cultural_population_structure.py tests/unit/test_cultural_similarity_metrics.py --cov=analysis --cov-report=term`.

## Phase Risks and Mitigations

- Carrier incidence and prevalence differ: persist both denominators and spell them out in specifications.
- Source fingerprints sometimes encode provenance: require compatible content projections; otherwise fidelity is unavailable.
- Dynamic groups create selection bias: fixed-cohort longitudinal comparison, with exclusions visible.

## Phase Completion Checklist

Tasks 4–6 pass their verification commands; only `index.md` records progress.
