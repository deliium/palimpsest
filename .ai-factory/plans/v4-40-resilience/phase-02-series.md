# Phase 2: Ten independent resilience time series

Plan: [index.md](index.md)  
Tasks: 4–5  
Depends on: Tasks 1–3.

## Objective

Produce auditable, separate shock-aligned series for all ten requested dimensions, with explicit units, denominators, coverage and baseline identities.

## Current-Code Evidence

| Path | Symbols | Why it matters |
|---|---|---|
| `src/analysis/regional_population.py`, `src/analysis/regional_migration_metrics.py` | `fold_regional_history`, `compute_regional_migration_metrics` | Living populations and raw arrival versus residence-qualified inference are distinct. |
| `src/analysis/overexploitation_history.py`, `src/world/models.py` | `build_overexploitation_history`, `Resource` | Do not use a pressure-only fold after a V4-39 stock shock or sum unlike stock units. |
| `src/agents/cognition/institution_concepts.py`, `src/agents/cognition/practical_knowledge.py` | `InstitutionConceptLedger`, `InstitutionConceptStatus`, `PracticalKnowledgeLedger`, `SubjectivePracticalKnowledge` | Typed owner exports distinguish recognized concepts and active knowledge; published report never holds these ledgers. |
| `src/analysis/institutional_persistence.py`, `src/analysis/cultural_technology_continuity.py` | `compute_institutional_persistence`, `compute_cultural_technology_continuity` | Broader episode/archive work is separate; v1 must not assert institutional collapse or technological extinction. |
| `src/analysis/inequality_indices.py`, `src/world/events.py` | `quantized_gini`, `Helped`, `Fed`, `ProjectContributed`, `ExchangeCompleted`, `JourneyArrived`, `Died` | Existing inequality quantization and objective flows. |
| `src/analysis/trade_networks_events.py`, `src/analysis/trade_networks_detection.py`, `src/world/infrastructure.py` | `trade_transfer_rows_from_events`, `detect_corridors`, `InfrastructureAsset` | V4-18's broader retrospective classifier is not an as-of exchange trajectory; infrastructure identity and status are separate. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/analysis/resilience_series.py` | Create | Closed dimensions, scope keys, integer measures, coverage and signed baseline differences. |
| `src/analysis/resilience_physical.py`, `src/analysis/resilience_social.py` | Create | Pure reducers, no runner or cognition imports. |
| `src/simulation/resilience_evidence.py`, `src/experiments/resilience_capture.py` | Modify | Finalize typed leaf projections and eligibility declarations. |
| `tests/unit/test_resilience_physical.py`, `tests/unit/test_resilience_social.py` | Create | Arithmetic, scope, coverage, censoring and false-recovery tests. |

## Task 4: Reduce physical and network response

### Intent

Separate shifts in population, physical movement, stocks, reuse of trade corridors, and availability of infrastructure.

### Implementation Steps

1. In `resilience_series.py` define fixed enum order: `population_recovery`, `migration`, `resource_recovery`, `institution_continuity`, `knowledge_retention`, `technology_loss`, `cooperation`, `inequality`, `trade_network_recovery`, `infrastructure_recovery`. Each episode has ten panels with exactly nine cells each in window order. `SeriesCell` includes absolute/relative interval via window index, status/reason, observed coverage, and a tuple of closed typed `Measure` leaves keyed by metric and optional scope. Measures contain integer/null `value`, units by metric, optional integer `numerator`, `denominator`, and nullable signed `delta_from_baseline`. Use Python integer arithmetic for ratios (`floor(1000*n/d)` for nonnegative fractions; null at `d=0`), and existing physical quantization for source amounts. Delta is current minus baseline in the same metric and exact scope with both values non-null; baseline delta is zero for defined values. No direction-to-good conversion or cross-dimension rollups. Sort by metric and then scope key; no generic maps of arbitrary metric names.
2. Implement pure `reduce_physical(inputs, episode, windows)` in `resilience_physical.py`. Calculate the five lanes below only from verified inputs; the report orchestrator merges lanes in the closed order. Use endpoint states for stock measures and half-open windows for flows. Build trade visit history **once** over the verified prefix (in event sequence), then aggregate with no look-ahead across window ends.

| Lane | Applicability, exact v1 measure, and source |
|---|---|
| Population recovery | Always applicable. `living` = count of objectively living registered bodies at the endpoint. `entries` = number of first registrations between the start/end boundary (founders at boundary zero are not entries); `deaths` = committed `Died` of registered bodies in the interval, deduped by body. `living_vs_baseline_milli` = endpoint living / pre-shock living, null at pre-shock zero or invalid baseline. Internal relocation never increases population. |
| Migration | Enabled only with `regions_migration`. `cross_region_arrivals` counts each `(journey_id, participant_body_id)` on committed `JourneyArrived` with two known, different regions; `unique_arrivals` counts distinct bodies; emit direction breakdown keyed by ordered `(origin_region_id,destination_region_id)` for both counts. A counted crossing is **not** a residence-qualified move or net population gain. An unmappable endpoint is `projection_gap`, not same-region movement. Do not count intent, `JourneyStarted`, waits, or deaths in transit as arrivals. |
| Resource recovery | Managed ecological stock only, grouped by exact `(resource_kind, unit)`; `managed_nodes`, `quantity_tenths`, and `effective_capacity_tenths` are endpoint counts/sums for each group. Use fixed managed IDs for change comparisons; missing/retyped baseline ID or unit mismatch makes the lane partial rather than shrinking the denominator. This uses actual post-disaster facts, not policy targets or nominal capacity. |
| Trade network recovery | `subjective_valuation` must be present. Emit `completed_exchanges`, `resolved_corridor_item_visits`, `first_seen_item_visits`, `active_corridors`, `baseline_corridors`, `baseline_corridors_active`, `baseline_corridor_share_milli`. Per item, predecessor is `unseen`, `known(venue)`, or `unknown_venue`. For each completed exchange (both sides, dedupe item within event), use `occurrence.origin_location_id` and emit an edge only from a known distinct predecessor. A known venue following `unseen` counts as first seen. A missing venue marks its slot partial and sets the affected items to `unknown_venue`; the next known visit of such an item also marks **its** slot partial (even in another window), creates neither first-seen nor edge, and resets the predecessor to known for future visits. No observably missing predecessor is rewritten by later events. Freeze baseline directed edges only when baseline trade coverage is complete; a new edge does not restore a baseline edge. This is an exchange-venue trajectory, not the broader V4-18 transfer/media classifier or a verified travel route. |
| Infrastructure recovery | Enabled iff the infrastructure channel is present. `operational_assets`, `baseline_assets` (distinct operational asset IDs at baseline), `baseline_assets_operational`, `baseline_asset_share_milli`, `new_operational_assets`, and `baseline_slots_reoccupied_by_new_assets` (distinct `(kind,location,endpoint)` slots with a new operational asset **and** no original asset operational; normalize edge endpoints for undirected topology). Destroyed or absent original IDs remain in the baseline denominator; repair can restore the ID, replacement is reported separately. Do not infer operation from project creations or an empty final snapshot of an off channel. |

3. Validate trusted projection data (overflow, duplicate identity, unknown region, missing venue, inconsistent body or source mapping). A known-empty fully covered lane may output zero counts. `baseline_*`-relative fields, including `living_vs_baseline_milli`, are null when the baseline does not qualify. Use sparse directional/grouped measure leaves: a direction absent in a complete cell has known zero; a direction observed only after shock can compare with that zero only if the baseline migration lane was complete. No special numerical fill for missing stock groups.
4. Also reduce the immediate point from only two boundary snapshots, `s` and `s+1`. The physical subset is `living`, `managed_nodes`, `quantity_tenths`, `effective_capacity_tenths`, and `operational_assets`; reuse existing scope, inventory and units. Preserve raw `s+1` values when the pre-point comparison is censored. No migration, trade, entries, deaths, or other flow summary in the immediate point.

### Required Interfaces and Contracts

- Phase 1 evidence DTOs plus pure episode/windows; no engine calls. Integer and typed scope keys only; no arbitrary labels or raw events in output. Scope is **one simulation run**, not a polity or society agent. No observer route or registered scalar family.
- Source evidence: user-requested five dimensions, existing V4-39 timing, `regions_migration`, ecology capacity, V3 structured barter, V4 infrastructure status.

### Error Handling and Logging

No reducer logging; return lane-local `partial`/`unavailable` for semantic projection gaps and closed `ResilienceError` for malformed detached inputs. No fractional baseline imputation, omitted-input zero, or future media reclassification.

### Tests / Acceptance / Verification

`tests/unit/test_resilience_physical.py`: zero population with entrants later, unchanged population despite cross-region arrivals, group transport counts, zero-vs-disabled migration, stock with unlike units and lower effective capacity, no window baseline on short run, an immediate stock dip gone by the first full post window, distinct items/hops/first visits, missing venue on the last tick of one slot and recovery of the predecessor on the first tick of the next, later exchange cannot rewrite earlier cells, destroyed vs repaired original infrastructure vs replacement and no baseline assets.

Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_resilience_physical.py -q`. Hand calculations match all raw counts and ratios.

## Task 5: Reduce owner-scoped and distributional response

### Intent

Measure continuity, retention, technology absence, cooperation and inequality without equating claims with objective institutions or sparse observations with confirmed loss.

### Implementation Steps

1. In `resilience_social.py` add pure `reduce_social(inputs, episode, windows)` with the rules below. Count a living source as eligible when complete or unsupported (active or not verifiably off); observed means complete, including fresh-empty. Put `eligible_owners` and `observed_owners` in coverage metadata, not numerical measures, so a partial cell can still disclose evidence shortfall. Use null counts only if the point itself is unverified; use zero for a verified empty roster. Death is only established by objective evidence, never by a missing runtime. A lane with zero eligible owners is `channel_off` if it has no established enabled owner scope in the episode up to that point. If baseline eligible owners die, known zero living holders is not an export gap. If a baseline owner is still alive but loses source eligibility, allow complete raw current inventory measures but withhold baseline-relative values as `baseline_owner_scope_changed`. For an unsupported eligible living source, keep owner coverage and mark the cell partial; do not publish numerical measures for that cell.
2. Copy only baseline/current keys required for the reduction. Institution keys are `(owner body ID, recognized concept ID)`; knowledge keys are `(owner body ID, active entry content_key)` (deduped per owner); technology uses the distinct `content_key` union over eligible living owners. A valid baseline fixes those three denominator sets separately. Never include these owner or content IDs in report output.

| Lane | Exact v1 measure |
|---|---|
| Institution continuity | `recognized_owner_concepts`, `baseline_recognized_owner_concepts`, `baseline_concepts_still_recognized`, `recognized_continuity_milli`. Count exact baseline keys still `RECOGNIZED`; `FADING`, `RETIRED`, owner death or a replacement ID do not count. Same owner key observed again counts at that point, not as uninterrupted continuity. This measures continuity of reported owner recognition, not an objective institution or a collapse verdict. |
| Knowledge retention | `active_owner_contents`, `baseline_active_owner_contents`, `baseline_owner_contents_retained`, `owner_content_retention_milli`. Reacquisition by the same owner can restore the presence count; uptake by another owner cannot, and is reflected only in the technology key union. |
| Technology loss | `living_technique_keys`, `baseline_technique_keys`, `baseline_technique_keys_missing`, `baseline_technique_keys_missing_milli`, `baseline_technique_keys_missing_two_points`. A missing key has no active living eligible holder; the final count requires absence at both the current and immediately previous **complete adjacent post points** (null for the first point or across gaps); observed return ends the absence. Never infer physical performability, loss from archives, irreversible extinction, or a causal effect of the shock. |
| Cooperation | Report committed assistance, feeding and project contributions separately as `helps`, `feeds`, `contributions`; record `person_ticks` as the sum of start-of-tick living registered population over the eight ticks. Compute each act's milli-per-person-tick rate from the corresponding count; distinguish eventless and zero person-ticks. `contributions` is unavailable with projects off (the other submeasures may remain complete); no opportunity-based compliance, gift intent, testimony, or composite cooperation value. |
| Inequality | Held-item count distribution among **all living registered bodies** at the endpoint, with explicit zero holdings. Emit `living_samples`, `total_held_items`, `zero_holders`, `held_item_gini_milli` via `analysis.inequality_indices.quantized_gini` for ≥2 samples (all-zero distribution gives 0; below 2 gives null). This is possession-count inequality, not ownership, wealth, class, welfare or access; no interpretation of mover/death composition as improving welfare. |

3. For structured count outputs retain numerator, denominator and source coverage when a rate is null due to a proven empty denominator. If complete evidence shows that cross-owner transmission preserves a technology key while losing an owner/content pair, report both results. Leave all other disabled/censored measures null, with whitelisted reason codes; do not fabricate a baseline.
4. The social subset at the immediate point is `recognized_owner_concepts`, `active_owner_contents`, `living_technique_keys`, `living_samples`, `total_held_items`, `zero_holders`, and `held_item_gini_milli`. Reuse endpoint eligibility and quantization, compare only to `s` when allowed, and emit no cooperation rate or technology-loss-duration measure there.

### Required Interfaces and Contracts

- `reduce_social` imports the neutral evidence contracts, not cognition. `ResilienceBoundaryFacts` is the producer boundary for validated ledger keys. Architecture allows result aggregation from private owner rows only in trusted research paths; no export to live cognition, stop criteria, or observer semantics.
- Source evidence: user-requested five dimensions, owner-scoped ledgers, inequality utility, committed physical assistance contributions; explicitly narrow proxies are declared in v1.

### Error Handling and Logging

Pure analysis, no row logging. Unsupported owner sources are lane-local coverage gaps. At cohort extinction distinguish world evidence of no living holders from failed extraction. Gaps break consecutive loss detection, and no adjacent complete point means the two-point count is unknown.

### Tests / Acceptance / Verification

`tests/unit/test_resilience_social.py`: recognized/fading/replacement/death, baseline knowledge retention vs cross-owner key survival, active/inactive/deduped rows, unsupported living source with counts retained, enabled fresh-empty and mixed newborn runtime modes, baseline owner still alive but source off, known complete extinction, loss/rediscovery and gap between two absences, assistance per person-ticks, projects off, `[0,2]` Gini = 500 and `[0,0]` = 0, population zero/one Gini null. Use Hypothesis for ratio bounds/deterministic canonical reduction and future-append invariance of already-complete windows and immediate points (later windows may become observed or censored).

Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_resilience_physical.py tests/unit/test_resilience_social.py -q`. A change in one evidence lane does not silently alter another's score—none exists.

## Phase Risks and Mitigations

- Apparent recovery can be a changing denominator or substitute. Publish denominators; keep baseline matches, novel assets and edges, and observed coverage separate.
- Counts are proxies. Do not label cross-region arrivals persistent migration, institutions objective, held items wealth, or technology absence extinction.

## Phase Completion Checklist

- Tasks 4–5 satisfy acceptance; focused tests pass; update their boxes only in `index.md`.
