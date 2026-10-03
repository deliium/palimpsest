# Implementation Plan: Expanded Analysis Beyond Raw V1 Metrics

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-03
Improved: 2026-10-03 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete milestone; this plan adds analysis-only phenomenon indicators and multi-seed comparative summaries over already-landed V2 arms without owning `multi_hop_testimony_tracking`.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M6 — Remaining V2 Capability Flags
INFO [aif-plan] mode=ultra treated as full (richer plan); remaining args describe the feature
INFO [aif-plan] resolved plan file: .ai-factory/plans/v2-expanded-analysis-beyond-v1-metrics.md (format=slug)
INFO [aif-plan] plan name prefix v2- applied per user request; git.create_branches=false so stem is description slug
INFO [aif-improve] applied refinement: lock new families + count 38, claim-id overlap, survival sibling doc, support_band rules, metric sidecars, inputs wiring, reputation distributional keys, analysis-owned matrix summary

## Compatibility contract

This plan expands the read-only `analysis` surface and matrix aggregation so researchers can quantify social/cultural/cognitive phenomena with measurable indicators, confidence intervals, and seed-wise comparative distributions. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants intact. `WorldEngine` remains the only objective mutation authority. Cognition still receives immutable per-agent `Observation` / `Perspective` only. Metric documents, phenomenon panels, and matrix summaries never feed collectors, aggregates, or treatment labels back into cognition, memory, prompts, or action selection.
2. Capability flags stay opt-in and default-off. Do **not** add a new `V2CapabilityFlags` slot. Do **not** own `multi_hop_testimony_tracking`. Do **not** introduce new cognition modes or runner-config schema bumps.
3. V1 regression gate stays green under flags-off and tracing-off. Catalog A–E and the reference scenario keep current trajectories. New families, panels, and matrix summaries stay **off** `tests/unit/test_v1_regression_gate.py`.
4. No scripted emergence. Forbidden: boolean `culture_emerged` / `norm_emerged` / `society_formed` fields, friend/enemy/leader/culture role labels on world/observation/commands, and single-threshold “emerged” declarations. Report measurable indicators, availability, and comparative distributions only.
5. No LLM → world shortcuts. Analysis consumes detached rows / harvested audits / committed events after the run.
6. Experiments stay reproducible. Cross-seed summaries must be deterministic for equal completed metric sets under `analysis.numerical` quantization (canonical quantized output, not BLAS bit-identity). Prefer NumPy / pandas / SciPy / NetworkX already allowed by the project.
7. Optional cognition tracing stays outside the objective fold. Summaries must not require tracing.
8. Observed metrics stay separate from agent-visible state. No metric document, panel, or summary may appear on `Observation`, `Perspective`, belief/relationship ledgers, or cognition stages.

## Goal

Expand analysis beyond raw per-run V1 metric scalars into a researcher-facing **phenomenon indicator** layer plus **multi-seed comparative distributions**.

Cover quantitative detection/measurement for:

| Phenomenon | Existing substrate (reuse) | This plan adds |
| --- | --- | --- |
| community structure | `group_community_structure@1` | panel wiring; keep NX greedy modularity |
| group persistence | `compute_group_persistence` / `emergent_group_formation@1` | panel wiring |
| network centrality | partial `centralization_out` only | degree / betweenness / closeness summaries + keyed export |
| reciprocity | `trust_network_structure@1` reciprocity | panel wiring |
| cooperation | `cooperation@1` | panel wiring |
| resource inequality | `resource_inequality@1` | panel wiring |
| specialization | `behavioral_specialization@1` | panel wiring |
| territorial concentration | `spatial_control@1` presence/control | new family `territorial_concentration@1` (HHI / top-share) |
| reputation divergence | `distributed_reputation@1` gaps | additive distributional keys on same family |
| belief convergence | `BeliefClaimRow` claim identity | new family `belief_convergence@1` |
| norm adoption | `emergent_social_norms@1` | panel wiring |
| convention persistence | `persistent_social_conventions@1` / `compute_convention_persistence` | panel wiring |
| cultural similarity | naming / norms / conventions / narratives ledgers | new family `cultural_similarity@1` |
| rumor/narrative mutation | `rumor_distortion@1` + `cultural_narrative_lineage@1` | panel wiring |
| vocabulary convergence | `emergent_semantic_naming@1` | panel wiring |
| survival differences | `survival@1` | sibling `survival_cohort_contrast@1` (legacy survival unchanged) |
| goal success | `goal_completion@1` | panel wiring |
| prediction calibration | `causal_world_model@1` / world-model audits | new family `prediction_calibration@1` |

Also support comparison across repeated seeded runs by extending matrix aggregation beyond cell refs into quantized distribution + CI summaries.

```text
Per-run MetricDocument (@1 families, enriched)
  → optional cells/<cell_id>.metrics.json sidecars (encoded documents)
  → PhenomenonIndicatorPanel (analysis-only; multi-indicator; no emergence booleans)
  → MatrixMetricSummary (analysis builder; across seeds / group_role / condition)
  → research_runner aggregate CLI (optional write)
```

## Locked scope decisions

1. **Reuse before rewrite.** Do not redefine formulas for existing families that already match the table above. Prefer new families or additive keys with explicit algorithm-version bumps when a formula changes.
2. **Catalog bump is additive and locked.** Current baseline at implement time was already **35** families (`cognitive_budget` registered while `METRIC_FAMILY_COUNT` still said 34). This plan registers exactly four new `MetricFamilyId` values — `territorial_concentration`, `prediction_calibration`, `belief_convergence`, `cultural_similarity` — and bumps count **35 → 39** (plan draft said 34→38; corrected for the pre-existing `cognitive_budget` drift). Sibling helper `survival_cohort_contrast@1` is a catalog family **only if** it is registered as a fifth id; prefer a non-catalog sibling document returned beside `survival@1` so count stays 38 (lock: **non-catalog sibling document**, not a fifth family). Do not silently reinterpret old documents. Keep schema `MetricDocument` version; pack new scalars into `values`.
3. **No emergence booleans.** `PhenomenonIndicatorPanel` may expose `support_band` codes `absent` / `weak` / `moderate` / `strong` from the locked multi-indicator rule table in Task 7 — never a single arbitrary threshold labeled “culture emerged”. Forbidden model field names: `emerged`, `culture_emerged`, `norm_emerged`, `society_formed`, `detected`.
4. **CIs are analysis-only.** Use deterministic percentile-based intervals and/or SciPy exact/binomial intervals where denominators are counts. Bootstrap, if used, must take an explicit seed stream derived from `stable_seed_tuple` — never Python `hash()` or wall clock. Document the interval method on the summary document.
5. **matrix-aggregate-v1 stays.** Keep the existing ref-only aggregate. Add sibling schema `matrix-metric-summary-v1` that carries per-key distributions. Do not break consumers of `matrix-aggregate-v1`.
6. **Libraries.** NumPy / pandas / SciPy / NetworkX only for scientific compute; follow `analysis.numerical` (float64 intermediates, sort-before-reduce, banker's quantization to 12 dp, signed-zero normalize, NA≠0). Centrality uses exact NetworkX algorithms with lexicographic node order — no approximation shortcuts.
7. **Assembly.** `assemble_metric_documents` continues to assemble the V1 core set. New opt-in families assemble when their detached inputs are present (same pattern as spatial). The phenomenon panel is a separate builder over already-computed `MetricDocument`s.
8. **Metric value sidecars for matrices.** Today `collector_fields_from_documents` stores only fingerprints/availability. Matrix summaries **must not** invent values from fingerprints. Persist optional `cells/<cell_id>.metrics.json` sidecars containing encoded `MetricDocument` payloads (or an equivalent allowlisted numeric snapshot) when catalog/opt-in metrics are collected. Summary builder reads sidecars only for documents that were actually computed.
9. **Package placement.** Pure `build_matrix_metric_summary` lives in `src/analysis/matrix_metric_summary.py`. Experiments / `research_runner` own filesystem I/O and CLI only (experiments may already import analysis).
10. **Off the V1 gate.** No new reference-scenario trajectory expectations for these families.
11. **Deferred (not this plan):** Fully populating every V1 objective evidence slice (`applied_actions`, resource holdings, etc.) from matrix runner harvests when those harvests are absent today. Sidecars cover documents successfully computed from available harvests/audits only. Godot observer charts, HTTP summary routes, SQLAlchemy summary storage, and owning `multi_hop_testimony_tracking` remain deferred.

## Design Decisions (locked)

### New catalog families (count 38)

| Family | Version | Primary inputs |
| --- | --- | --- |
| `territorial_concentration` | `territorial_concentration@1` | detached presence / control spatial rows |
| `prediction_calibration` | `prediction_calibration@1` | world-model hypothesis snapshots (+ optional confidence rows) |
| `belief_convergence` | `belief_convergence@1` | ordered `BeliefClaimRow`-shaped rows |
| `cultural_similarity` | `cultural_similarity@1` | duck-typed naming/norm/convention/narrative channel rows |

`spatial_control@1` and `causal_world_model@1` algorithms/value keys stay unchanged.

### Belief overlap identity

Convergence overlap tokens are derived from `(claim_id, value_kind, normalized value)` on existing `BeliefClaimRow` fields (`claim_id`, `value_kind`, `bool_value` / `categorical_value` / `numeric_value`). Do **not** invent a free-text `claim_fingerprint` field. Never use claim/proposition text.

### Survival cohort contrast

`compute_survival` / `survival@1` remain bit-identical when no cohort map is supplied. Cohort contrasts are a **sibling** helper returning a separate `MetricDocument` (family string `survival_cohort_contrast`, algorithm `survival_cohort_contrast@1`) that is **not** registered in `MetricFamilyId` / does not bump `METRIC_FAMILY_COUNT`. Empty/missing cohort map → no sibling document (not zeros on survival).

### Reputation distributional keys

Keep existing `reliability_gap` / `harm_gap` / `generosity_gap` / `competence_gap` bit-identical. Add additive keys on `distributed_reputation@1`: `neighborhood_count`, `mean_pairwise_gap`, `max_pairwise_gap` (quantized; absent when `<2` neighborhoods).

### Phenomenon `support_band` rules

Published data in `phenomenon_specifications` (not UI copy):

| Band | Rule |
| --- | --- |
| `absent` | fewer than 1 present indicator for the phenomenon |
| `weak` | exactly 1 present indicator (allowed only for unary mappings such as reciprocity) **or** ≥2 present but all below their weak floor |
| `moderate` | ≥2 present indicators and at least half meet their moderate floor |
| `strong` | ≥2 present indicators and all meet their strong floor |

Per-indicator floors are explicit floats in the mapping table (direction-aware: higher-is-stronger vs lower-is-stronger). No path may emit a boolean “emerged” label from a single threshold.

### Matrix metric sidecars

```text
<root>/cells/<cell_id>.json              # existing state sidecar
<root>/cells/<cell_id>.completion.json   # existing completion identity
<root>/cells/<cell_id>.metrics.json      # NEW optional encoded MetricDocument[] 
```

- Written only when at least one present/partial metric document was assembled for the cell.
- Canonical JSON via existing `encode_metric_document`; sorted by `metric_family`.
- Missing sidecar → that cell contributes no numeric rows to `matrix-metric-summary-v1` (not zeros).
- Fingerprint-only `CollectorMetricDocument` fields remain unchanged for `matrix-aggregate-v1`.

## Commit Plan
- **Commit 1** (after tasks 1–3): `feat(analysis): add centrality, concentration, and calibration metric families`
- **Commit 2** (after tasks 4–6a): `feat(analysis): add belief convergence, cultural similarity, reputation distribution, and survival cohort contrast`
- **Commit 3** (after tasks 6b–9): `feat(analysis): wire opt-in metric inputs and phenomenon indicator panels`
- **Commit 4** (after tasks 10–12b): `feat(analysis): add multi-seed metric distribution summaries and cell sidecars`
- **Commit 5** (after tasks 13–14): `test(analysis): prove indicator panels and matrix summary isolation`

## Tasks

### Phase 1: Per-run metric gaps (network, territory, prediction)

- [x] Task 1: Extend trust-network centrality exports and add per-node centrality summaries.
  - Deliverable: Align `trust_network_structure@1` so `centralization_out` is a locked `value_keys` entry (today it is computed but omitted from the spec key tuple). Add additive keys for nonnegative-projection summaries: `mean_degree_centrality`, `mean_betweenness_centrality`, `mean_closeness_centrality` (exact NetworkX, lexicographic node order, self-loops dropped). Empty / single-node graphs follow existing unknown/absent policy — never coerce to zero. Keep algorithm tag `@1` unless an existing key formula changes. Unit fixtures cover empty, one-node, reciprocal dyad, and star graphs.
  - Files: `src/analysis/network_metrics.py`, `src/analysis/specifications.py`, `tests/unit/test_network_metrics.py`, `tests/unit/test_metric_specifications.py`.
  - Logging: DEBUG family id, node/edge counts, which centrality keys are present/absent; never log node id lists at INFO; never log trust payloads.
  - Dependencies: None.

- [x] Task 2: Add `territorial_concentration@1` as a new catalog family.
  - Deliverable: **Locked:** new family `territorial_concentration@1` in its own module. Register `MetricFamilyId.TERRITORIAL_CONCENTRATION` and bump catalog toward final count 38 (with Tasks 3–5). Compute Herfindahl–Hirschman index and top-1 / top-3 location shares over living-agent presence ticks and, separately, over objective control events when rows exist. Missing rows → `ABSENT`, not zeros. Leave `compute_spatial_control` / `spatial_control@1` claim contest logic and value keys unchanged.
  - Files: `src/analysis/territorial_concentration_metrics.py` (new), `src/analysis/specifications.py`, `src/analysis/__init__.py`, `tests/unit/test_territorial_concentration_metrics.py`.
  - Logging: DEBUG location cardinality and which share keys are present; WARNING empty rows with reason `no_spatial_rows`; no location name strings.
  - Dependencies: None.

- [x] Task 3: Add prediction calibration family from harvested hypothesis / confidence evidence.
  - Deliverable: New family `prediction_calibration@1`. Inputs: detached causal-hypothesis snapshots (from `world_model_audits` / same audit shape as `causal_world_model@1`) and optional prospective/memory confidence rows when present, joined to committed empirical outcomes after the run. Locked keys: `brier_score` (squared-error mean), `mean_absolute_calibration_error` over fixed confidence bins (document bin edges in the spec), `evaluated_count`, `bin_count_used`. Degenerate empty → `ABSENT`. Do not invent engine probabilities; confidence is the subjective score already on the snapshot. Leave `causal_world_model@1` value keys unchanged.
  - Files: `src/analysis/prediction_calibration_metrics.py` (new), `src/analysis/specifications.py`, `src/analysis/__init__.py`, `tests/unit/test_prediction_calibration_metrics.py`.
  - Logging: DEBUG evaluated/bin counts and availability; never log hypothesis atoms, proposition text, or full confidence vectors.
  - Dependencies: None.

### Phase 2: Belief / culture / reputation / survival contrasts

- [x] Task 4: Add belief convergence family from detached claim rows.
  - Deliverable: New family `belief_convergence@1`. From ordered `BeliefClaimRow` (or duck-typed equivalent) rows, build per-owner active claim sets using overlap identity `(claim_id, value_kind, normalized value)` — **no** `claim_fingerprint` field and no claim text. Compute pairwise Jaccard trajectories and locked keys: `mean_pairwise_jaccard_final`, `mean_pairwise_jaccard_delta`, `owner_count`, `claim_universe_size`. Unevaluable / empty → `ABSENT`. No truth specs required (convergence ≠ accuracy). Must not import cognition or mutate beliefs.
  - Files: `src/analysis/belief_convergence_metrics.py` (new), `src/analysis/specifications.py`, `src/analysis/__init__.py`, `tests/unit/test_belief_convergence_metrics.py`.
  - Logging: DEBUG owner/claim cardinalities and availability; never log claim text.
  - Dependencies: None.

- [x] Task 5: Add cultural similarity family and reputation distributional keys.
  - Deliverable: (a) New family `cultural_similarity@1` joining caller-supplied detached rows from naming bindings, norm heads, convention habits, and/or narrative variant fingerprints (duck-typed `getattr`). Locked keys: per-channel mean pairwise similarity plus `channels_present` count. Missing channel → that channel key `ABSENT` without zeroing others. Forbidden: a single blended “culture score” presented as emergence. Leave per-channel `@1` family algorithms unchanged. (b) On `distributed_reputation@1`, keep existing `*_gap` keys bit-identical and add `neighborhood_count`, `mean_pairwise_gap`, `max_pairwise_gap`. Finalize `METRIC_FAMILY_COUNT = 38` after Tasks 2–5 registrations.
  - Files: `src/analysis/cultural_similarity_metrics.py` (new), `src/analysis/reputation_metrics.py`, `src/analysis/specifications.py`, `src/analysis/__init__.py`, `tests/unit/test_cultural_similarity_metrics.py`, `tests/unit/test_reputation_metrics.py` (or extend existing).
  - Logging: DEBUG which channels contributed and reputation neighborhood counts; WARNING when all channels empty; never log label/norm/narrative tokens or dimension payloads at INFO.
  - Dependencies: None.

- [x] Task 6: Add survival cohort contrast as a sibling document.
  - Deliverable: Keep `survival@1` population keys bit-identical when no cohort map is supplied (unit-prove fingerprints). Add sibling helper `compute_survival_cohort_contrast(survival_agents, cohort_id → agent_ids, ...)` returning a separate `MetricDocument` with `metric_family="survival_cohort_contrast"`, algorithm `survival_cohort_contrast@1`, keys `max_cohort_gap`, `cohort_count` (and unknown when any cohort denominator is empty). **Not** registered in `MetricFamilyId`. Cohorts are researcher labels only — never friend/enemy/culture roles and never written onto agents. Missing cohort map → return `None` / omit document.
  - Files: `src/analysis/objective_metrics.py`, `src/analysis/__init__.py`, `tests/unit/test_objective_metrics.py` (or survival-specific).
  - Logging: DEBUG cohort_count and gap availability; never log agent id lists at INFO.
  - Dependencies: None.

- [x] Task 6b: Wire opt-in family inputs into `MetricComputationInputs` and composition mappers.
  - Deliverable: Extend `MetricComputationInputs` with optional detached fields for territorial concentration rows, belief-convergence claim rows, cultural-similarity channel rows, prediction-calibration audit rows, reputation ledgers/neighborhoods, and survival cohort maps. Assemble new families in `assemble_metric_documents` (or a thin adjacent assembler used by collectors) **only when** those fields are present — same pattern as `spatial_action_rows`. Add composition helpers that map existing harvests where available (e.g. `world_model_audits` → calibration/causal inputs; spatial events → concentration rows) without inventing missing objective slices. Default empty inputs leave new families absent and must not change V1 catalog trajectories when flags-off.
  - Files: `src/analysis/metric_service.py`, `src/experiments/composition.py`, `src/experiments/collectors.py` / `metric_collection.py` as needed, `tests/unit/test_metric_service.py`, composition/collector unit tests.
  - Logging: DEBUG which optional input blocks were attached (counts only); WARN skip with reason codes when harvests missing; never log claim/audit payloads.
  - Dependencies: Tasks 2–6.

### Phase 3: Phenomenon indicator panel (no emergence booleans)

- [x] Task 7: Define `phenomenon-indicators-v1` contracts and locked mapping table.
  - Deliverable: Frozen slotted models for `PhenomenonId` (closed StrEnum covering the eighteen phenomena in the Goal table), `PhenomenonIndicatorRef` (family + value key + direction + weak/moderate/strong floors), `PhenomenonIndicatorReading`, and `PhenomenonIndicatorPanel`. Mapping table lists ≥2 indicator refs per phenomenon where substrate exists (single-ref only when genuinely unary, e.g. reciprocity). Implement the locked `support_band` rule table from Design Decisions. Explicitly forbid fields named `emerged`, `culture_emerged`, `norm_emerged`, `society_formed`, or `detected`.
  - Files: `src/analysis/phenomenon_models.py` (new), `src/analysis/phenomenon_specifications.py` (new), `src/analysis/__init__.py`, `tests/unit/test_phenomenon_specifications.py`.
  - Logging: Log-free models/specs (same pattern as `MetricSpecification`); validation errors expose stable reason codes only.
  - Dependencies: Tasks 1–6 (family ids and additive keys registered).

- [x] Task 8: Implement `build_phenomenon_indicator_panel` over `MetricDocument` sequences.
  - Deliverable: Pure function that selects indicator values by family/key, records `MetricAvailability`, applies the locked support_band rules, and emits a canonical panel document. Missing families → indicator `ABSENT` (not zero). Must not recompute NetworkX/pandas from raw evidence — only read already-built documents. Prove panels cannot be imported into `agents`, `agents.cognition`, or passed into `AgentRuntime` / observation builders (architecture test).
  - Files: `src/analysis/phenomenon_panel.py` (new), `src/analysis/__init__.py`, `tests/unit/test_phenomenon_panel.py`, `tests/architecture/` isolation updates as needed.
  - Logging: INFO panel build with phenomenon count and present/absent tallies; DEBUG per-phenomenon support_band codes; never log metric payloads at INFO.
  - Dependencies: Task 7.

- [x] Task 9: Wire optional panel assembly into experiment collectors after metric bundles.
  - Deliverable: After catalog / opt-in `MetricBundle` assembly in collectors (not inside V1 `assemble_metric_documents`), call `build_phenomenon_indicator_panel(bundle.documents)` and attach the panel as an analysis-only artifact beside metric documents (e.g. encode next to the metrics sidecar or a dedicated panel field on the arm result). Default catalog A–E path unchanged when the panel is skipped (`insufficient_metric_documents`). No HTTP routes. No observer frame fields in this plan.
  - Files: `src/experiments/collectors.py`, `src/experiments/composition.py` only if a mapper helper is needed, `tests/unit/test_phenomenon_panel_wiring.py` (or extend collector tests). Prefer keeping panel separate from V1 assemble.
  - Logging: DEBUG whether panel attached; WARN skip with reason `insufficient_metric_documents`.
  - Dependencies: Tasks 1–6, 6b, 8.

### Phase 4: Multi-seed comparative distributions and CIs

- [x] Task 10: Add numerical helpers for distribution summaries and confidence intervals.
  - Deliverable: Pure helpers in `src/analysis/distribution_summary.py` (keep `numerical.py` free of logging/callers): sorted finite sample → `n`, `mean`, `std_sample`, `median`, `p05`, `p95`, and an interval method (`percentile` and/or SciPy binomial/proportion CI for rate-like keys). Unknown/NA samples dropped with `dropped_non_finite` count — never coerced to zero. Deterministic; document method codes on outputs.
  - Files: `src/analysis/distribution_summary.py` (new), `src/analysis/numerical.py` (reuse quantize/require_finite only), `src/analysis/__init__.py`, `tests/unit/test_distribution_summary.py`.
  - Logging: Log-free helpers; callers log counts only.
  - Dependencies: None.

- [x] Task 11: Persist optional per-cell metric document sidecars.
  - Deliverable: When matrix/catalog collection produces a `MetricBundle` with at least one present/partial document, write `cells/<cell_id>.metrics.json` as canonical encoded documents (sorted by family) via the matrix manifest store. Extend store port with `write_metric_documents` / `read_metric_documents`. Missing sidecar is valid (cell contributes no numeric summary rows). Do not put full metric payloads into `CollectorMetricDocument` fields (fingerprints stay metadata-only for `matrix-aggregate-v1`).
  - Files: `src/experiments/matrix_manifest.py`, `src/experiments/matrix_runner.py` and/or collectors wiring, `tests/unit/test_experiment_matrix_metric_sidecars.py`.
  - Logging: INFO sidecar write with cell_id prefix and document count; DEBUG family list; never log value payloads at INFO.
  - Dependencies: Task 6b.

- [x] Task 12: Implement `matrix-metric-summary-v1` builder in analysis.
  - Deliverable: Pure `build_matrix_metric_summary(...)` in `src/analysis/matrix_metric_summary.py`. Group by `condition_id` / `group_role` / `metric_family` / `value_key`, aggregate numeric values across seed×replicate cells using Task 10 helpers. Preserve cell/run ids as sorted opaque ids only. Fail closed on mixed algorithm versions for the same family/key. Leave `build_matrix_aggregate` behavior unchanged. Thin experiments wrapper loads sidecars and supplies grouping metadata.
  - Files: `src/analysis/matrix_metric_summary.py` (new), `src/experiments/matrix_metric_summary.py` (thin I/O wrapper), `src/analysis/__init__.py`, `src/experiments/__init__.py`, `tests/unit/test_matrix_metric_summary.py`.
  - Logging: INFO summary build with condition/family/key counts; DEBUG interval method codes; never log full value vectors at INFO.
  - Dependencies: Tasks 10, 11.

- [x] Task 12b: Extend `research_runner` aggregate CLI to optionally emit metric summaries.
  - Deliverable: `palimpsest-matrix aggregate` gains a flag (e.g. `--metric-summary`) to write `matrix-metric-summary-v1` JSON beside (not replacing) `matrix-aggregate-v1`, reading metric sidecars from the manifest root. Default keeps current aggregate-only behavior. Still must not import `api`.
  - Files: `src/research_runner/cli.py`, `src/research_runner/composition.py`, `tests/unit/test_research_runner_cli.py`.
  - Logging: CLI INFO for output path and key counts; never print metric payloads by default.
  - Dependencies: Tasks 11, 12.

### Phase 5: Docs, proofs, isolation

- [x] Task 13: Documentation checkpoint (`Docs: yes`).
  - Deliverable: Update `docs/analysis-metrics.md` with new families (count 38), survival sibling contrast, reputation additive keys, phenomenon panel rules (explicit “no culture_emerged” + support_band table), CI/distribution methods, and the mapping table. Update `docs/experiments.md` for metric sidecars, `matrix-metric-summary-v1`, and CLI flag. Append a Downstream V2 note in `docs/architecture.md` that panels/summaries/sidecars are analysis-only and off the V1 gate. Brief `.ai-factory/DESCRIPTION.md` / `ARCHITECTURE.md` inventory lines if package file lists require it. Update `.ai-factory/ROADMAP.md` M6 to list this plan as started/implemented when done; keep `multi_hop_testimony_tracking` as the remaining flag. Route through `/aif-docs` conventions during implement.
  - Files: `docs/analysis-metrics.md`, `docs/experiments.md`, `docs/architecture.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/ROADMAP.md` as needed.
  - Logging: N/A for docs prose; examples must show metadata-safe commands.
  - Dependencies: Tasks 8, 11, 12, 12b.

- [x] Task 14: Architecture, determinism, and V1 regression confirmation.
  - Deliverable: Tests proving (a) panel/summary modules are not importable from domain cognition paths, (b) equal completed metric sidecar sets → identical summary fingerprints, (c) missing evidence/sidecars stay `ABSENT`/`unknown` not zero, (d) no `culture_emerged` (or similar) field exists on panel models, (e) `tests/unit/test_v1_regression_gate.py` remains green without new gate cases, (f) catalog validation passes with `METRIC_FAMILY_COUNT == 38`, (g) survival fingerprints unchanged without cohort map, (h) reputation legacy `*_gap` keys unchanged when only additive keys are exercised. Network-free fixtures only.
  - Files: `tests/unit/test_metric_specifications.py`, `tests/unit/test_metric_determinism.py` (extend), `tests/architecture/` isolation, `tests/unit/test_v1_regression_gate.py` (run only).
  - Logging: Assert log extras exclude payloads/claim text where existing audit patterns apply.
  - Dependencies: Tasks 1–13.

## Implementation notes for `/aif-implement`

- Prefer extending specs with additive keys when bit-identical legacy values matter; add new families when the semantics are distinct (calibration ≠ causal match counts; concentration ≠ claim contest).
- Phenomenon `support_band` rules must be published in `phenomenon_specifications` as data, not buried in UI copy.
- Reputation divergence panel refs use both legacy `*_gap` and new distributional keys; Task 5 must not replace `distributed_reputation@1`.
- Group persistence / convention persistence helpers already exist — panel wiring only unless keys are missing from documents.
- Matrix metric summaries consume encoded/decoded `MetricDocument` values already quantized; do not re-quantize with a different policy.
- Do not expand fingerprint-only collector fields into full payloads; sidecars are the numeric path.
- Deferred follow-ups (not this plan): full objective evidence harvest for every V1 family in matrix cells, Godot observer charts for panels, HTTP metric summary routes, SQLAlchemy storage of summaries, owning `multi_hop_testimony_tracking`.
