# Phase 4: Population, demographics and generation navigation

Plan: [index.md](index.md)  
Tasks: 9–11  
Depends on: Tasks 2, 3, 7, 8

## Objective
Deliver the first complete research workflow: choose run → navigate generation or tick → inspect population/demographics → compare cohorts.

## Current-Code Evidence
| Path | Symbols | Why it matters |
|---|---|---|
| `src/api/routes/observer.py` | demographics and generation-marker GET routes | Reuse existing objective projections |
| `src/simulation/observer_demographics.py` | demographic projection/cursors | Feature-off differs from enabled zero; pages have exact whole-population totals |
| `src/analysis/generational_cohort.py` | `compute_generational_cohort_comparison` | Already stored metrics; do not recalculate scientific comparisons in UI |
| `clients/research-ui/src/views/MatrixPanel.svelte` | list/detail loaders | Existing matrix screen currently renders metadata keys only |
| `clients/godot-observer/fixtures/protocol/generational/markers.json` | actual-admission markers | Shared real protocol fixture |

## Files to Change
Introduce `clients/research-ui/src/components/research/GenerationNavigator.svelte`, `EvidenceLegend.svelte`, `AvailabilityNotice.svelte`, `SeriesChart.svelte`, `ResearchTable.svelte`, `MetricCard.svelte`; `src/research/population.ts`, `cohorts.ts`; `src/views/PopulationPanel.svelte`, `CohortsPanel.svelte` and sibling tests. Modify RunOverview, MatrixPanel and Shell styles for responsive research width.

## Task 9: Build accessible common charts and generation/tick navigator
### Intent
Reuse visual primitives with consistent coverage and epistemic semantics instead of adding a plotting library.
### Implementation Steps
1. Implement SVG line/step/bar series with finite/null inputs, axes/units, point selection callbacks and a paged accessible data table. Gap segments have no connecting line; class is shown by badge/text/stroke pattern, not color alone. Include title/description and keyboard-selectable points. No smoothing or invented values.
2. Build generation previous/next/dropdown alongside an explicit tick field. Obtain finalized discovery high-water H from `getObserverRun` (`GET /observer/run`), independent of selected tick T. Discover/paginate actual-admission markers with `tick=H`, preserving returned revision throughout the marker list. If only T is known, report discovery pending/unavailable rather than treating T's marker set as the complete run. Selecting a marker changes T to its server-provided seek tick but keeps H, so Next remains usable after seeking backward. Refresh H only on explicit refresh/run-context reload; never silently advance T. Do not derive `generation * interval` or pedigree depth.
3. Generation-only URL resolves through markers; explicit tick takes precedence when both exist. If it conflicts with the selected marker, show `generation_tick_mismatch` and preserve the explicit tick. Tick changes do not guess an exclusive generation because generations overlap. Nonexistent generation stays unresolved with explanation.
4. Prefix cursor remains tick+sequence; generation selection explicitly clears sequence/event and seeks a finalized boundary. Prefix-only data cannot drive finalized lineage/capture panels; show a button to move to full tick, never silently switch.
### Required Interfaces and Contracts
Chart props: typed series `{id,label,evidenceClass,ownerId,unit,points,coverage,sourceRef}`; point `{tick,value|null,generationIndex?}`. Navigator emits selection patch, never HTTP control. Founders use generation0; missing generations are not synthesized.
### Requirement Evidence
User generation/tick navigation; `docs/observer.md` actual-admission semantics and prefix limitations.
### Error Handling and Logging
Unavailable lifecycle renders tick navigation plus disabled generation selector; debug denial does not disable objective navigation. Safe selection metadata only.
### Tests
Mounted SVG/table equivalence, keyboard selection, null gaps, legend text, generation0/multiple cohorts/denied admission, marker pagination, generation-only resolution, tick conflict and event-prefix clearing. A run complete through H with generations0/1/2 must allow starting at T=0, navigating Next→1→2→Previous→1 without rediscovering at T; concurrent high-water refresh cannot append mixed-revision marker pages.
### Acceptance Criteria
Both navigation modes work independently; generation selection lands on the actual finalized admission boundary; charts remain usable without color or mouse.
### Verification
`pnpm --dir clients/research-ui test src/components/research`; `pnpm --dir clients/research-ui check`.

## Task 10: Render population timeline and demographic charts
### Intent
Make the existing demographic API useful as a research dashboard, without conflating registered population and bodies.
### Implementation Steps
1. `population.ts` adapts agents/cohorts/generations envelopes and exact whole-population totals. Use one point per resolved boundary for admitted/living/dead; never sum repeated totals across pages. Separate stage/life-status bars, generation distribution and paged agent/cohort tables.
2. `PopulationPanel.svelte` includes the navigator, explicit range/sample control from Task8, line/step chart, current-boundary summary, stage chart and selected-agent details. Agent age is displayed only when available; dead age is unknown, not extrapolated.
3. Load summary once per boundary; fetch additional agent/group pages on demand. Chart series are labelled objective-world; page truncation and stage truncation get distinct notices. Clicking agent opens agent focus/lineage with preserved time.
### Required Interfaces and Contracts
Current API totals are authoritative for that resolved cursor. Sparse samples show sampled population levels, not inferred birth/death rates. Demographic cohort is not biological kinship. Point selection updates global tick; no direct simulation commands.
### Requirement Evidence
User population timeline/demographic charts; `ObserverDemographicsOut` semantics and `test_observer_demographic_api.py` invariants.
### Error Handling and Logging
Lifecycle-disabled, replay-unavailable and enabled zero produce different displays. Keep old samples visibly partial on continuation failure; reset on run change.
### Tests
Real demographics agents/cohorts fixtures; totals unchanged after page append; stages truncated, dead-age null, zero versus disabled; point→tick navigation and stale-response cancellation. Test sampled missing tick does not become zero.
### Acceptance Criteria
Population lines and demographic bars show numeric data, not JSON dumps; exact totals and paging agree.
### Verification
`pnpm --dir clients/research-ui test src/research/population.test.ts src/views/PopulationPanel.test.ts`.

## Task 11: Add cohort and repeated-run comparison views
Depends explicitly on Task1's composite cohort selection, in addition to Tasks4,7–10.

### Intent
Compare real cohorts while keeping descriptive within-run tables separate from repeated-seed experimental inference.
### Implementation Steps
1. `cohorts.ts` builds descriptive admitted/living/dead and living/admitted proportion rows at the same explicit boundary from paged cohort/generation projections. Key cohort rows by `(run_id,generation_index,entry_tick,cohort_id)` and preserve the tuple through URL selection, table keys, chart series and comparison joins; repeated cohort labels/IDs must not merge. Zero denominator yields null; label this census survival share, not Kaplan–Meier survival or causal effect.
2. `CohortsPanel.svelte` selects at least two cohorts/generations, shows aligned bars/table, entry ticks, differing ages/exposure and provenance. Generation and cohort selectors are separate. URL cohort keys are `cohort_generation_index`, `cohort_entry_tick`, `cohort_id`; preserve independent navigation `generation_index`. ID-only legacy selections resolve only with exactly one matching loaded cohort; ambiguous/incomplete selection requires clarification in UI, not first-match selection.
3. Extend MatrixPanel to render actual metric rows for `generational_cohort_comparison@1` and cultural artifacts via metric-set-aware adapters. Generational metrics use existing scalar keys; cultural documents use parsed `values.rows_json`. Comparison payloads have `conditions[*].measurements[*]` and `contrasts[*]`: read exact `measurement` selectors, `n`, `raw_cell_count`, `duplicate_cell_count`, `mean`/`mean_difference`, `ci_low/high`, `df`, `inference_status`, seed blocks, exclusions, and paired `shared_stream_status`/`channel_alignment`. Show method/confidence/window/units and render intervals only when supplied with a compatible inferential status. Do not invent a comparison self-digest. Legacy p05/p95 remain descriptive percentiles; never derive inference from a single selected run or a PARTIAL measurement.
4. Cell links open the run only when a validated result contains a run ID; missing link becomes an explanation, not guessed filesystem identity. Cohort comparison remains functional without matrix storage.
### Required Interfaces and Contracts
UI transforms stored values into charts only; no new metric definitions/calculators. Selectors include family/algorithm/policy/measurement ID/dimension/representation/scope/partition/groups/population basis/denominator/window/units; row IDs are not cross-run comparison keys. Incompatible selectors render separate `not_comparable` facets. Runtime-bound versus legacy-unverified artifact binding stays visible; valid self-digests alone do not prove completed execution. No unsupported causal wording.
### Requirement Evidence
`docs/generational-runner.md` and `docs/cultural-evolution-metrics.md`; existing matrix summaries and seed-block intervals.
### Error Handling and Logging
Missing artifact leaves descriptive comparison usable. Invalid metric set does not discard other valid sets. DEBUG family/count/window status only.
### Tests
Same cohort ID reused across entries and generations, URL reload selecting the exact tuple, two cohorts same generation, nonfounder entries, zero denominator, distinct exposure and multiple metric sets. Real BM/V3-cultural documents exercise scalar versus `rows_json` adapters, one seed, repeated-seed intervals, duplicate numeric seed blocks, `uncontrolled_provider_variation`, PARTIAL rows, legacy percentiles, unverified binding and incompatible selectors. Assert actual encoded comparison field names, not a parallel synthetic frontend shape.
### Acceptance Criteria
Within-run cohort and repeated-run scientific comparisons are both visible with noninterchangeable labels and denominators.
### Verification
`pnpm --dir clients/research-ui test src/research/cohorts.test.ts src/views/CohortsPanel.test.ts src/views/MatrixPanel.test.ts`.

## Phase Risks and Mitigations
Sampling cost is bounded by Task8. A generation label does not imply age-aligned or kin-related cohorts; copy and denominators make this explicit.

## Phase Completion Checklist
Behavioral chart/navigation/cohort tests pass; update index only.
