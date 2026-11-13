# Implementation Plan: Economic Inequality

Branch: main
Created: 2026-11-13

## Original Request

v4-24 inequality

Naming requirement:

Use `v4-24-economic-inequality`.

Implement longitudinal metrics for:

- resource possession

- productive tool access

- infrastructure access

- storage access

- credit relationships

- organizational resource control

Support measures such as distributions and inequality indices where appropriate.

Keep ownership legitimacy separate from physical possession/control.

Add cohort and society comparisons.

## Settings

- Testing: yes; full strategy. Unit, architecture, determinism, integration,
  Compose config/browser, Godot regression (existing suite only), Research UI,
  benchmark regression, and static gates, with coverage enabled for Python lanes.
- Logging: verbose, metadata-only. Bounded DEBUG window/owner/row counts,
  detection milestones, and selected status tokens; INFO analysis composition
  and publication milestones; WARN truncation, partial coverage, unresolved
  strata, malformed frames, and oversize rows; ERROR safe codes.
  `PALIMPSEST_LOG_LEVEL` controls verbosity. Never log owner tokens, society
  tokens, item ids, quantities, indices, distributions, cohort labels, cursor
  keys, digests, credentials, DSNs, memories, embeddings, or payload surrogates.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 19.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints are suggestions, not authorization to
  commit during planning or implementation unless the user explicitly asks.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-24-economic-inequality`; this plan is the single
  full-mode artifact `.ai-factory/plans/v4-24-economic-inequality.md`. Python
  tokens use `economic_inequality` / `economic-inequality-*`; the feature name is
  "economic inequality".
- Research source: `.ai-factory/RESEARCH.md` and `.ai-factory/research/` do not
  exist; no external research conclusions are invented.
- Execution: plan only in this invocation. No implementation, commit, roadmap
  edit, or branch creation occurs while planning.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"
Rationale: V4-24 adds a fifteenth, analysis-only V4 context that measures
economic inequality over already-owned objective and owner-scoped economic
seams; it claims no V4 capability flag, runner schema, command, event, write
pair, API version, or migration, and it does not close M8 or edit other
milestones.

## Requirements Reconciliation

Authority: the Original Request defines scope. `.ai-factory/ARCHITECTURE.md`
("Key Principles", "Versioned Extension Contract", V3-11, V3-12, V3-17, V3-18,
V3-19, V3-20, V3-21, V4-02, V4-03, V4-04, V4-08, V4-15, V4-18 through V4-23
seams) and `.ai-factory/RULES.md` constrain every edit. `.ai-factory/DESCRIPTION.md`
describes the implemented state; `.ai-factory/ROADMAP.md` is stale for V4-23 and
V4-24 and stays owned by `$aif-roadmap`. Concrete contracts come from the source
paths below. No requirement source is edited to create this plan.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-24 declares a fifteenth V4 context `economic_inequality` with authority `detached_analysis`, owning package `analysis`, seam `analysis_capture`, and no capability flag; contexts 14 -> 15, flags stay 12, owned stay 8, unowned stay 4, map revision becomes `v4-context-map-v3` | Original Request "metrics"; `src/simulation/v4_architecture.py:38-56,60-106,287-332,367-417` | Task 1/18/21 |
| The new context must be added to `V4_ANALYSIS_ONLY_CONTEXTS` and to `V4_EVENT_REUSING_CONTEXTS`; it may not own a reserved or deepening write pair and needs no migration stage | `src/simulation/versioning.py:93-115,129-175`; `src/simulation/migration_plan.py:37-126` | Task 1/18 |
| No `runner-config-v57`, runner root field, per-agent key, capability flag, command, event, observer semantic type, write pair, `/v2` route, or SQL migration is added; `runner-config-v56` remains the accepted seam | `src/simulation/compatibility.py:154-166`; `src/simulation/runner_models.py:1128-1179`; `.ai-factory/ARCHITECTURE.md` V4-23 seam | Task 1/18/21 |
| Six metric dimensions are measured independently: `resource_possession`, `productive_tool_access`, `infrastructure_access`, `storage_access`, `credit_relationship`, `organizational_resource_control`; no dimension is pooled into a composite wealth, ownership, or legitimacy score | Original Request; `src/analysis/objective_metrics.py:187-376`; `src/analysis/specifications.py:667-731` | Task 2/5/8/17 |
| Physical possession and access use committed objective evidence only: item custody transitions, owner location transitions, operational infrastructure assets, store structures, and repositories; no `WorldState`, runtime, store, or API object is read | `src/world/events.py:604-656,1035-1237,1708-1750,1994-2097,2777-2860`; `src/analysis/trade_networks_events.py:1-90` | Task 3/6/16 |
| Ownership legitimacy is a separate owner layer: credit claims come from committed `crd_v1` relations, organizational resource control comes from detached organization operation rows, and neither can substitute for objective possession or control | Original Request "Keep ownership legitimacy separate"; `src/analysis/credit_relationships_events.py:127-236`; `src/analysis/organization_operations.py:126-209,413-454` | Task 4/7/17 |
| Cohorts are generation cohorts derived from committed `AgentCreated.generation_index`; bootstrap agents are generation 0. Society comparisons use detached `msoc-` analytical records over their recorded window indexes. Overlap is legal; no partition, ranking, best/worst label, or civilization score exists | Original Request "cohort and society comparisons"; `src/world/events.py:1708-1750`; `src/analysis/macro_society_identity.py:47-90`; `src/analysis/inter_society_relations_detection.py:96-196` | Task 6/7/8 |
| Longitudinal windows are 32 ticks with at most 512 windows; each dimension reports a per-window distribution (min, p25, median, p75, max, IQR, dispersion, five bin shares in milli) and quantized Gini, Theil T, Atkinson eps=1, and top-share indices | Original Request "distributions and inequality indices"; `src/analysis/objective_metrics.py:187-245`; `src/analysis/accounting_ledgers_detection.py:286-348`; `src/analysis/accounting_ledgers_policy.py:55-56` | Task 5/8/17 |
| Eight metric families append 220 -> **228**: six dimension families plus cohort and society comparison families. The first 220 ids, order, versions, and value keys stay unchanged | `src/analysis/specifications.py:52-53,72-297,9030-9077,9527-9570,10081-10139`; `src/analysis/metric_service.py:405-413,2660-2688` | Task 8/18/20/21 |
| Analysis activates only when committed events exist and at least one economic channel is present (`organizations`, `markets_credit`, `infrastructure_networks`, `supply_chains`, `durable_records`, `structured_commitments`, or `subjective_valuation`); otherwise no analysis, metric input, or snapshot field is produced and off-path behavior is unchanged | Original Request; `src/experiments/collectors.py:287-327`; `.ai-factory/ARCHITECTURE.md` Key Principle 4 | Task 9/15/18 |
| Snapshot is a sibling `economic-inequality-snapshot-v1` with store `economic-inequality-store-v1`, two dual-gated settings, window-bound cursors, and seven GET-only routes failing closed with `economic_inequality_disabled`; it is not a runner/result/replay/SQL schema | `src/simulation/trade_networks_models.py:454-536`; `src/simulation/accounting_ledgers_ports.py:17-84`; `src/persistence/accounting_ledgers_filesystem.py:225-247`; `src/infrastructure/settings.py:264-267,493-502,913-925` | Task 10/11/12/13/21 |
| Publication is programmatic and post-completion; no CLI producer and no runner flag is added | `src/experiments/accounting_ledgers_publication.py:88-272`; V4-20/V4-21/V4-22/V4-23 have no CLI producer | Task 12/21 |
| No Godot overlay is added: inequality is detached analysis, not a presentation fact; the presentation client is unchanged and its existing suite is the regression gate | Original Request; `.ai-factory/ARCHITECTURE.md` V3-40 through V3-42 seam | Task 14/18/21 |
| Off-gate experiment `economic_inequality@1` composes existing flags/specs in three arms and never enters the V1 A-E gate | `src/experiments/catalog.py:244-252,2800-2838,5712-5730`; `src/experiments/accounting_ledger_scenario.py:43-149` | Task 15/21 |
| Documentation covers `docs/economic-inequality.md`, README, ARCHITECTURE, DESCRIPTION, `docs/architecture.md`, `docs/configuration.md`, `docs/analysis-metrics.md`, `docs/research-api.md`, `docs/v4-architecture.md`, `docs/research-ui.md`, and cross-links in `docs/organizations.md`, `docs/credit-relationships.md`, and `docs/supply-chains.md`; roadmap registration stays with `$aif-roadmap` | `.ai-factory/ARCHITECTURE.md` requirement 7; `.ai-factory/ROADMAP.md`; `docs/accounting-ledgers.md` structure | Task 19/20/21 |

### Supported combinations and coverage transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| No economic channel and no relevant spec | Untouched run | No analysis, no `economic_inequality_*` metric input, no snapshot field | Task 9/18 |
| Any economic channel, committed events present | Detached evidence harvest | Dimension rows only where evidence exists; missing dimensions are `unavailable`, never zero-filled | Task 3/4/16 |
| Objective possession observed, no owner claims | Objective distribution | Claim dimensions `unavailable`; objective rows never borrow claimed quantities | Task 4/7/17 |
| Owner claims observed, no objective possession | Claim distribution | Objective dimensions `unavailable`; claimed counts never labeled possession | Task 4/7/17 |
| Fewer than four observed owners in a window/measure | `insufficient_samples` | Row retains counts and no invented quantile/index | Task 5/8/17 |
| Four or more observed owners | `available` | Counts, five quantiles, IQR, dispersion, five bin shares, Gini/Theil/Atkinson/top-share | Task 5/8/17 |
| One to three observed owners | `insufficient_samples` | Counts retained; no quantile, index, or share is invented | Task 5/17 |
| All observed values zero | `available` | Indices 0, shares 0, coverage reported | Task 5/17 |
| Missing recipe output/structure kind mapping | Dimension `unavailable` | No guessed tool/storage classification; notice emitted | Task 3/9 |
| Missing owner location evidence | Access dimensions exclude that owner | Coverage `partial`; no location inference | Task 3/17 |
| Missing cohort membership | Cohort family `unavailable` | No fabricated cohort | Task 6/8 |
| Missing society membership | Society family `unavailable` | No fabricated `msoc-` row | Task 6/8 |
| Overlapping society membership | Rows retained | `overlap_member_count` counted; no partition | Task 6/17 |
| Cap exceeded for events, owners, rows, cohorts, or societies | Deterministic prefix | `coverage="partial"` plus one bounded notice per family | Task 2/3/4/10/17 |
| Snapshot dual gate unset | No reader | 503 `economic_inequality_disabled` on all seven routes | Task 11/13 |
| Corrupt snapshot payload | No data | 500 `economic_inequality_store_corrupt` | Task 11/13 |
| Paged route with `window_index` | Filter-bound cursor | Only matching rows; cursor for another window rejected 400 | Task 10/13 |
| Publication disabled by the caller | No artifact | Nothing written; scientific status unchanged | Task 12 |
| Env-gated lane missing prerequisite | No green certification | `unexecuted` plus prerequisite | Task 21 |

No blocking open questions: every material decision is fixed below.

## Architecture and Decisions

1. **Add one analysis-only context, claim no flag.** `economic_inequality` is a
   detached analytical context. It owns no world state, no owner state, and no
   capability slot. Counts become 15 contexts / 12 flags / 8 owned / 4 unowned.
2. **Measure, never adjudicate.** The surface reports distributions and
   inequality indices over observed quantities. It never asserts legitimate
   ownership, desert, merit, fault, poverty status, or a welfare ranking.
3. **Physical evidence is objective.** Possession comes from effect-complete
   committed custody transitions. Access comes from observed location plus
   operational infrastructure, store structures, and repositories. No
   `WorldState`, inventory object, runtime, store, or API object is read.
4. **Legitimacy is an owner layer.** Credit claims come from committed `crd_v1`
   relations; organizational resource control comes from detached organization
   operation rows. These rows are tagged as claims and never netted against
   physical possession.
5. **Six independent dimensions.** Each dimension has its own evidence,
   denominator, and rows. There is no composite wealth index and no cross-
   dimension aggregation.
6. **Longitudinal windows.** `window_ticks=32`, `max_windows=512`. Every
   dimension row carries its window index and tick. Metric documents summarize
   the latest window, window count, and a closed trend direction.
7. **Quantized indices.** Gini, Theil T, Atkinson eps=1, and top-share reuse the
   existing `resource_inequality` formulas and quantization. Shares are integer
   milli. No float payloads appear in the snapshot beyond quantized values.
8. **Cohorts are generations.** Generation index comes from committed
   `AgentCreated`; bootstrap owners are generation 0. A cohort row exists only
   when its membership and at least four observed owners exist.
9. **Societies are detached candidates.** Society membership comes from
   detached `msoc-` analytical records applied to their recorded window
   indexes. Overlap is legal; society rows are compared by distribution of
   their own Gini values, never ranked.
10. **Bounded everything.** Events, owners, dimension rows, cohorts, societies,
    comparison rows, notices, and snapshot bytes have independent caps with
    deterministic prefixes and `coverage="partial"`.
11. **Activation is opt-in.** No economic channel means no analysis and no
    metric documents, so default V1/V2 bundles are unchanged.
12. **Read-only surfaces.** `economic-inequality-snapshot-v1` is canonical,
    digest-addressed, and wall-clock-free. `economic-inequality-store-v1` is
    atomic, quota-bounded, idempotent, and corruption-safe. Seven GET-only
    dual-gated routes serve it. Publication is programmatic after completion.
13. **No presentation physics.** No Godot overlay and no client write path; the
    Research UI panel is read-only.
14. **Catalog discipline.** Eight families append exactly at positions 220-227;
    every active pin and doc footer is swept from 220 to 228 in one change.

### Locked economic-inequality summary

| Dimension | Locked behavior |
| --- | --- |
| Policy | `economic-inequality.v1` (analysis and snapshot share the token) |
| V4 ownership | New analysis-only `economic_inequality`; 15 contexts / 12 flags / 8 owned / 4 unowned; map `v4-context-map-v3` |
| Runner schema | `runner-config-v56` only; no v57, no new root/per-agent key |
| Activation | Committed events **and** any of `organizations`, `markets_credit`, `infrastructure_networks`, `supply_chains`, `durable_records`, `structured_commitments`, `subjective_valuation`; otherwise disabled |
| Dimensions | `resource_possession`, `productive_tool_access`, `infrastructure_access`, `storage_access`, `credit_relationship`, `organizational_resource_control` |
| Measures | `observed_item_count`, `observed_tool_count`, `accessible_infrastructure_count`, `accessible_storage_count`, `claimed_principal_quantity`, `observed_repayment_quantity`, `claimed_relationship_count`, `claimed_resource_control_count`, `claimed_storage_control_count` |
| Layers | objective physical possession/access, owner claim, analytical comparison; hard separation guard |
| Window | 32 ticks; index `tick // 32`; at most 512 windows |
| Distribution | owner count; min/p25/median/p75/max; IQR; dispersion; five bin shares in milli; minimum 4 samples |
| Indices | Gini, Theil T, Atkinson eps=1, top-share; quantized; no composite |
| Trends | `rising`, `falling`, `stable`, `insufficient_samples`, `unavailable`; 50-milli change threshold |
| Cohorts | generation index from `AgentCreated`; at most 32 cohorts |
| Societies | detached `msoc-` records over their recorded window indexes; overlap legal; at most 2,048 societies |
| Caps | 200k events per family; 4,096 owners; 4,096 dimension rows; 4,096 comparison rows; 32 cohorts; 2,048 societies; 8 notices |
| Snapshot | `economic-inequality-snapshot-v1`; store `economic-inequality-store-v1`; 16 publications / 8 MiB; no wall-clock field |
| Routes | 7 GET-only under `SUBJECTIVE_DEBUG`; default limit 100; max 500; `window_index` <= 511; `economic_inequality_disabled` when unset |
| Catalog | 220 -> 228 families; first 220 unchanged; active suite and docs pins swept to 228 |
| Clients | Research UI panel; no new Godot overlay |
| Experiment | `economic_inequality@1`, off the V1 gate, three arms |
| Pins | 43 commands; 73 observer semantics; replay-v27/codec `v25`; Alembic `0017`; `/v1`; `observer-protocol-v1` |

## Tasks

### Phase 1: Registry, Contract, and Evidence

- [x] Task 1: Register the analysis-only `economic_inequality` V4 context
  - Add `V4ContextId.ECONOMIC_INEQUALITY`, a `V4ContextSpec` after
    `MACRO_SOCIETY_IDENTITY` with `capability_flag=None`,
    `authority=DETACHED_ANALYSIS`, `owner_packages=("analysis",)`,
    `existing_mechanism="resource possession, access, credit claims, and organization operations"`,
    `required_config_seam=V4_ANALYSIS_CAPTURE_SEAM`,
    `uses_existing_events=True`, `prerequisite_contexts=()`, and non-goals for
    "no objective wealth/ownership metric", "no composite inequality score",
    "no feedback into cognition, prompts, memory, admission, or stop selectors".
  - Change `_REQUIRED_CONTEXT_COUNT` to 15 and
    `V4_CONTEXT_MAP_VERSION` to `v4-context-map-v3`.
  - Add the id to `V4_ANALYSIS_ONLY_CONTEXTS` and to
    `V4_EVENT_REUSING_CONTEXTS` in `src/simulation/versioning.py`; do not touch
    write-pair reservations, deepening pairs, migration stages, runner models,
    or compatibility ownership tuples.
  - Files: `src/simulation/v4_architecture.py`,
    `src/simulation/versioning.py`; tests
    `tests/architecture/test_v4_context_registry.py` and
    `tests/architecture/test_v4_architecture_invariants.py`.
  - Logging: DEBUG registry validation count and context token; INFO
    `economic_inequality_context_registered`; ERROR stable validator codes.
  - Depends on: none.

- [x] Task 2: Lock the analysis contract, policy, caps, and DTOs
  - Create `src/analysis/economic_inequality_contract.py`: closed
    `EconomicInequalityDimension`, `EconomicInequalityMeasure`,
    `EconomicInequalityLayer`, `EconomicInequalityAvailability`
    (`available`, `insufficient_samples`, `unavailable`),
    `EconomicInequalityTrend`, `EconomicInequalityComparisonKind`; error class
    `EconomicInequalityError`; forbidden result fields (`wealth`, `net_worth`,
    `ownership`, `ownership_score`, `legitimate_owner`, `merit`, `poverty`,
    `rank`, `score`); `assert_economic_inequality_layer_separation`.
  - Create `src/analysis/economic_inequality_policy.py` with
    `EconomicInequalityAnalysisPolicy` defaults: `window_ticks=32`,
    `max_windows=512`, `min_distribution_samples=4`, `max_event_rows=200_000`,
    `max_owners=4_096`, `max_dimension_rows=4_096`,
    `max_comparison_rows=4_096`, `max_cohorts=32`, `max_societies=2_048`,
    `max_notices=8`, `trend_threshold_milli=50`; helpers
    `window_index_for_tick`, `validate_window_index`.
  - Create `src/analysis/economic_inequality_rows.py` with token-only DTOs:
    `EconomicPossessionRow`, `EconomicAccessRow`, `EconomicCreditClaimRow`,
    `EconomicControlClaimRow`, `EconomicCohortMembership`,
    `EconomicSocietyMembership`, `EconomicLayerBundle`,
    `EconomicDimensionWindowRow`, `EconomicCohortRow`, `EconomicSocietyRow`.
    Owner tokens use `eio-<16 hex>` derived from the stable owner id; no raw
    owner ids in snapshot-facing rows.
  - Files above plus `src/analysis/__init__.py`.
  - Tests: `tests/unit/test_economic_inequality_contract.py`,
    `tests/unit/test_economic_inequality_policy.py`,
    `tests/unit/test_economic_inequality_layers.py`.
  - Logging: DEBUG accepted/rejected row counts; WARN `truncated` notices; ERROR
    `economic_inequality_invalid_input` and reason codes.
  - Depends on: 1.

- [x] Task 3: Extract committed possession and access evidence
  - Create `src/analysis/economic_inequality_events.py`. Read committed
    `WorldEvent` values only and reconstruct:
    - item custody from `ItemCrafted.resulting_holder_id`,
      `Taken.resulting_holder_id`, `Given.resulting_holder_id` (falling back to
      `recipient_id`), both sides of `ExchangeCompleted` (`give_item_ids` and
      `take_item_ids` with their kind arrays), `Dropped`,
      `ItemStored.consumed_item_id`, `Eaten.item_id`,
      `CraftStarted.consumed_item_ids`, `StructureBuilt.consumed_item_id`,
      `StructureRepaired.consumed_item_id`, and
      `ResourceHarvested.created_item_id`;
    - owner locations from `event.occurrence.origin_location_id` plus
      `Moved.resulting_location_id`, retaining the last known location when a
      later event omits it;
    - item kinds from `ItemCrafted.recipe_id` through an optional
      `recipe_output_kinds` mapping and from `ExchangeCompleted` kind arrays;
      unknown kinds stay `unknown` and are excluded from tool counts;
    - tool access as held items whose known kind is `ItemKind.TOOL`;
    - infrastructure access from `InfrastructureConstructed`, `Repaired`,
      `Damaged`, `Decayed`, `Destroyed`: map `asset_kind` to
      `InfrastructureKind`, `status` to `InfrastructureStatus`, and count only
      assets where `effects_active(status=..., integrity=..., kind=...)` is true
      at the owner's location;
    - storage access from `StructureBuilt` with an optional
      `recipe_structure_kinds` mapping (`StructureKind.STORE`) and from
      `RepositoryEstablished` location rows; count distinct assets by
      `structure_id` when a repository links a store structure so a repository
      is not counted twice, and treat access as physical presence, never
      permission.
  - Emit `EconomicPossessionRow` and `EconomicAccessRow` sorted by
    `(tick, owner_token)`. Unknown kinds or locations mark the relevant
    dimension `unavailable` or `partial`; never guess.
  - Files above; tests `tests/unit/test_economic_inequality_events.py`,
    `tests/unit/test_economic_inequality_events_properties.py`.
  - Logging: DEBUG event count, accepted rows, unknown-kind count, owner count;
    WARN `economic_inequality_unknown_item_kind`,
    `economic_inequality_missing_location`; ERROR stable codes on malformed
    events.
  - Depends on: 2.

- [x] Task 4: Extract committed credit and detached organizational-control claims
  - Create `src/analysis/economic_inequality_claims.py`. Build
    `EconomicCreditClaimRow` from
    `analysis.credit_relationships_events.credit_evidence_rows_from_events`
    without copying counterparty or item ids into snapshot rows; build
    `EconomicControlClaimRow` from detached
    `analysis.organization_operations.OrganizationOperationHarvestRows`,
    counting distinct organizations for `resource_control` and `storage`
    controls and retaining stance/contest counts only as claim metadata.
  - Map raw owner ids to `eio-` tokens. Keep claim rows in their own layer; never
    expose a claim row as possession.
  - Files above; tests `tests/unit/test_economic_inequality_claims.py`,
    `tests/unit/test_economic_inequality_claims_leakage.py`.
  - Logging: DEBUG credit claim count, control claim count, owner count; WARN
    unresolved org anchors; ERROR `economic_inequality_claim_invalid`.
  - Depends on: 2, 3.

- [x] Task 5: Add quantized inequality indices and distribution summaries
  - Add public helpers in `src/analysis/inequality_indices.py`:
    `quantized_gini` (delegating to the existing
    `resource_inequality_gini`), `quantized_theil_t`,
    `quantized_atkinson_eps_1`, `quantized_top_share`, and
    `inequality_distribution_summary` returning nearest-rank p25/median/p75,
    IQR, dispersion, five bin shares in integer milli, and sample count. Define
    nearest-rank quantiles, integer-milli bin rounding, and explicit
    one-sample/all-zero/empty behavior. Do not change existing
    `resource_inequality` output.
  - Create `src/analysis/economic_inequality_detection.py` to build per-window,
    per-measure vectors, skip windows with fewer than four observed owners as
    `insufficient_samples`, and compute rows deterministically.
  - Files above; tests `tests/unit/test_inequality_indices.py`,
    `tests/unit/test_economic_inequality_detection.py`,
    `tests/unit/test_economic_inequality_detection_properties.py`.
  - Logging: DEBUG window/measure vector counts; INFO
    `economic_inequality_detection_complete`; WARN `insufficient_samples` and
    `out_of_range` counts; ERROR non-finite/numerical codes.
  - Depends on: 2, 3, 4.

### Phase 2: Analysis, Comparisons, and Metrics

- [x] Task 6: Compose cohort and society comparisons
  - Create `src/analysis/economic_inequality_comparisons.py`.
    - Cohort rows group owners by generation index; bootstrap owners are
      generation 0. Require at least four observed owners per cohort.
    - Society rows group owners by detached `msoc-` record membership over each
      record's `window_indexes`. Overlap is retained and `overlap_member_count`
      counts owners in more than one society once.
    - Compute each stratum's own distribution and indices; compare stratum Gini
      values by distribution (median, IQR, range) and by longitudinal change
      (`rising`/`falling`/`stable`) using the 50-milli threshold. Never rank,
      label best/worst, or produce a composite score.
  - Files above; tests `tests/unit/test_economic_inequality_comparisons.py`,
    `tests/unit/test_economic_inequality_comparisons_properties.py`.
  - Logging: DEBUG cohort/society counts, comparable strata, overlap count; WARN
    `economic_inequality_insufficient_cohorts`,
    `economic_inequality_insufficient_societies`; INFO
    `economic_inequality_comparisons_complete`.
  - Depends on: 5.

- [x] Task 7: Compose the bounded `EconomicInequalityAnalysis` harvest
  - Create `src/analysis/economic_inequality_analysis.py` with
    `EconomicInequalityAnalysis` carrying `window_tick`, policy version,
    coverage fields, `dimension_rows`, `cohort_rows`, `society_rows`,
    `layers`, `notices`, and counts. Add
    `harvest_economic_inequality_analysis(*, possession_rows, access_rows,
    credit_rows, control_rows, cohort_memberships, society_memberships,
    policy=None, window_end=None)`.
  - Apply independent caps with deterministic prefixes, one notice per family,
    and `coverage="partial"`. Invoke
    `assert_economic_inequality_layer_separation` over objective, claim, and
    analytical groups. Empty evidence returns an empty analysis, not zeros.
  - Files above plus `src/analysis/__init__.py`; tests
    `tests/unit/test_economic_inequality_analysis.py`,
    `tests/unit/test_economic_inequality_bounds.py`.
  - Logging: DEBUG counts per layer and family; INFO
    `economic_inequality_analysis_complete windows=<n> rows=<n>`; WARN truncation
    and partial coverage notices; ERROR stable codes.
  - Depends on: 3, 4, 5, 6.

- [x] Task 8: Append eight metric families (220 -> 228) and wire the service
  - Add `MetricFamilyId` members after `ACCOUNTING_FLOW_STRUCTURE`:
    `RESOURCE_POSSESSION_INEQUALITY`,
    `PRODUCTIVE_TOOL_ACCESS_INEQUALITY`,
    `INFRASTRUCTURE_ACCESS_INEQUALITY`, `STORAGE_ACCESS_INEQUALITY`,
    `CREDIT_RELATIONSHIP_INEQUALITY`,
    `ORGANIZATIONAL_RESOURCE_CONTROL_INEQUALITY`,
    `ECONOMIC_INEQUALITY_COHORTS`,
    `ECONOMIC_INEQUALITY_SOCIETY_COMPARISON`.
  - Add three key tuples before `_trade_spec`:
    `ECONOMIC_INEQUALITY_DIMENSION_KEYS`
    (`economic_inequality_window_tick`, `window_count`, `owner_count`,
    `observed_owner_count`, `gini_latest`, `theil_t_latest`,
    `atkinson_eps_1_latest`, `top_share_milli_latest`, `median_latest`,
    `iqr_latest`, `trend_direction`, `coverage`, `availability`);
    `ECONOMIC_INEQUALITY_COHORT_KEYS`
    (`economic_inequality_window_tick`, `cohort_count`,
    `comparable_cohort_count`, `gini_median_milli`, `gini_iqr_milli`,
    `gini_range_milli`, `widening_count`, `narrowing_count`, `stable_count`,
    `insufficient_count`, `coverage`, `availability`);
    `ECONOMIC_INEQUALITY_SOCIETY_KEYS`
    (`economic_inequality_window_tick`, `society_count`,
    `comparable_society_count`, `gini_median_milli`, `gini_iqr_milli`,
    `gini_range_milli`, `above_pooled_median_count`,
    `below_pooled_median_count`, `equal_pooled_median_count`,
    `overlap_member_count`, `coverage`, `availability`).
  - Every dimension spec uses `evidence_inputs=frozenset({EvidenceStage.OBJECTIVE_EVENT_STATE})`;
    `ORGANIZATIONAL_RESOURCE_CONTROL_INEQUALITY` additionally declares
    `EvidenceStage.AGENT_VISIBLE_PROJECTION` and
    `EvidenceStage.BELIEF_REVISION_TESTIMONY`, mirroring
    `_spec_organization_operations`. All eight use
    `cohort_window="economic_inequality_window_tick"`,
    `deceased_policy="exclude_owners_strictly_after_death"`,
    `zero_holding_policy="observed_zero_included_unobserved_unknown"`,
    `self_edge_policy="not_applicable"`,
    `censoring_policy="insufficient_samples_remain_explicit"`,
    `empty_case="unavailable_unknown"`, `one_case="insufficient_samples"`,
    `all_zero_case="emit_zero"`, `unknown_case="unavailable_unknown"`, and
    `availability_behavior="explicit_unknown_without_economic_evidence"`.
    Populate `formulas={key: key.replace("_", " ") for key in keys}` exactly as
    the credit/accounting/trade helpers do; `MetricSpecification.__post_init__`
    rejects empty `formulas` or `evidence_inputs`.
  - Add eight `_spec_*` builders, append them to `_BUILDERS`, and set
    `METRIC_FAMILY_COUNT = 228`. Do not reorder, rename, or re-version the first
    220.
  - Create `src/analysis/economic_inequality_metrics.py` with eight
    `compute_*` functions returning `MetricDocument`:
    `compute_resource_possession_inequality`,
    `compute_productive_tool_access_inequality`,
    `compute_infrastructure_access_inequality`,
    `compute_storage_access_inequality`,
    `compute_credit_relationship_inequality`,
    `compute_organizational_resource_control_inequality`,
    `compute_economic_inequality_cohorts`, and
    `compute_economic_inequality_society_comparison`; import them in
    `metric_service.py`, add
    `economic_inequality_analysis: EconomicInequalityAnalysis | None` to
    `MetricComputationInputs`, and add one emit block logging
    `economic_inequality_metrics_emitted families=8 catalog=228`.
  - Map the analysis contract to metric-document vocabulary: `available` with
    full coverage -> `MetricAvailability.PRESENT`; `available` with partial
    coverage -> `MetricAvailability.PARTIAL`; `insufficient_samples` and
    `unavailable` -> `MetricAvailability.UNKNOWN` with distinct `notes_code`
    values. Build `MetricCoverage(observed=..., expected=..., ratio=...)` from
    each family's owner/stratum counts and never fabricate zeroes for missing
    evidence.
  - Files: `src/analysis/specifications.py`, `src/analysis/metric_service.py`,
    `src/analysis/economic_inequality_metrics.py`, `src/analysis/__init__.py`.
  - Tests: `tests/unit/test_economic_inequality_metrics.py`,
    `tests/unit/test_economic_inequality_catalog.py`,
    `tests/unit/test_metric_specifications.py`.
  - Logging: INFO family emission count and catalog token; DEBUG disabled path
    when no analysis input; ERROR metric calculation codes.
  - Depends on: 7.

- [x] Task 9: Wire completed-run inputs and collector injection
  - Create `src/experiments/economic_inequality_completed_run.py` with
    `build_completed_run_economic_inequality_analysis(runner_result, *,
    runner_config, committed_events, run_id, macro_society_analysis=None,
    organization_operation_rows=(), policy=None, window_end=None)`. Map:
    committed events; optional `recipe_output_kinds` and
    `recipe_structure_kinds` derived from
    `runner_config.agents[0].cognition.production_catalog` (empty catalog or
    mismatched catalogs yield no mapping, never a guess); detached
    `OrganizationOperationHarvestRows`; credit rows from committed claims;
    generation membership from `AgentCreated`; society membership from
    `MacroSocietyAnalysis.records` and their `window_indexes`.
  - Inject in `src/experiments/collectors.py` only when committed events exist
    and an economic channel is present:
    `flags = arm.assignment.runner_config.v4_capability_flags`;
    `config = arm.assignment.runner_config`; enable when any of
    `flags.organizations`, `flags.markets_credit`, `flags.infrastructure_networks`,
    `flags.supply_chains` is true, or `config.durable_records`,
    `config.structured_commitments`, `config.subjective_valuation` is not None.
    Log a bounded disabled token otherwise.
  - Wrap the completed-run call in the collector's existing try/except pattern:
    catch analysis or event-shape errors, log an ERROR safe code and counts
    only, and leave `inputs.economic_inequality_analysis=None` so a malformed
    optional input cannot fail a completed run.
  - Files above; tests
    `tests/unit/test_economic_inequality_completed_run.py`,
    `tests/unit/test_economic_inequality_collector.py`.
  - Logging: DEBUG input counts and enabled/disabled token; INFO
    `economic_inequality_collector_injected`; WARN missing seams; ERROR safe
    code only.
  - Depends on: 7, 8.

### Phase 3: Artifact, Publication, and Read Surfaces

- [x] Task 10: Add snapshot models, codec, paging, and ports
  - Create `src/simulation/economic_inequality_models.py` with
    `ECONOMIC_INEQUALITY_SNAPSHOT_VERSION = "economic-inequality-snapshot-v1"`,
    `ECONOMIC_INEQUALITY_SNAPSHOT_POLICY = "economic-inequality.v1"`,
    `MAX_ECONOMIC_INEQUALITY_DIMENSION_ROWS = 4_096`,
    `MAX_ECONOMIC_INEQUALITY_COHORT_ROWS = 1_024`,
    `MAX_ECONOMIC_INEQUALITY_SOCIETY_ROWS = 2_048`,
    `MAX_ECONOMIC_INEQUALITY_SNAPSHOT_BYTES = 8_388_608`,
    `EconomicInequalitySummaryRecord`, a dimension record covering all six
    dimensions and their measures, cohort and society records,
    `EconomicInequalitySnapshot`, and `empty_economic_inequality_snapshot`.
    Export the snapshot, codec, paging, and port symbols from
    `src/simulation/__init__.py` like the trade-network and accounting siblings.
  - Create `economic_inequality_codec.py` (`canonical_economic_inequality_json`,
    `economic_inequality_digest`, `compute_economic_inequality_publication_id`,
    `finalize_economic_inequality_snapshot`, `encode_/decode_`),
    `economic_inequality_paging.py`
    (`ECONOMIC_INEQUALITY_PAGE_DEFAULT=100`, `..._MAX=500`, pure page
    functions whose sort keys include `(window_index, dimension, measure)` or
    `(window_index, stratum)`), and `economic_inequality_ports.py`
    (reader/publisher protocols,
    cursor, query fingerprint, `purposes` for `summary`, `dimensions`,
    `possession`, `access`, `claims`, `cohorts`, `societies`).
  - Canonical encoding rejects duplicate/unknown keys, re-encodes to verify
    bytes, sorts rows deterministically, and enforces the 8 MiB cap. No
    wall-clock field.
  - Files above; tests `tests/unit/test_economic_inequality_snapshot.py`,
    `tests/unit/test_economic_inequality_codec.py`,
    `tests/unit/test_economic_inequality_paging.py`, and
    `tests/unit/test_economic_inequality_ports.py`.
  - Logging: DEBUG row counts and byte size; WARN cap/truncation; ERROR
    `economic_inequality_snapshot_invalid` and codec codes.
  - Depends on: 7, 8.

- [x] Task 11: Add the atomic store and dual-gated settings
  - Create `src/persistence/economic_inequality_filesystem.py` with
    `ECONOMIC_INEQUALITY_STORE_VERSION = "economic-inequality-store-v1"`,
    `EconomicInequalityPublisherOptions(max_publications=16,
    max_bytes=8_388_608)`, and `create_economic_inequality_{reader,publisher}`.
    Follow the `state.json` + `store.lock` + `flock` + `mkstemp`/`fsync`/
    `os.replace` convention; identical republish is idempotent; errors are
    `*_publication_exists`, `*_store_quota_exceeded`, `*_store_corrupt`.
  - Add `economic_inequality_root` and `economic_inequality_cursor_key`
    (`SecretStr`, >= 32 UTF-8 bytes) plus four bootstrap flags
    (`has_*_root`, `has_*_cursor_key`, `*_enabled`, `*_cursor_enabled`) in
    `src/infrastructure/settings.py`. Add `economic_inequality_root` to the
    `empty_presentation_root_is_unset` field-validator list so a blank
    `PALIMPSEST_ECONOMIC_INEQUALITY_ROOT` is unset rather than an invalid path.
  - Enforce both per-publication and cumulative byte quotas across publications;
    a test must publish several artifacts and assert the cumulative limit, not
    only one oversized payload.
  - Files above; tests `tests/unit/test_economic_inequality_store.py`,
    `tests/unit/test_economic_inequality_settings.py`.
  - Logging: INFO `economic_inequality_store_ready`, publication accepted;
    WARN quota; ERROR corruption/safe codes; never log paths' secrets.
  - Depends on: 10.

- [x] Task 12: Compose and publish completed-run snapshots
  - Create `src/experiments/economic_inequality_publication.py` with
    `compose_economic_inequality_snapshot(analysis, *, run_id)`,
    `publish_economic_inequality_snapshot(analysis, *, run_id, publisher)` and
    `build_economic_inequality_harvest_result(...)`. Map analysis rows only;
    finalize digest and publication id; emit an empty finalized snapshot when
    the analysis has no rows. Derive the summary's `truncated` flag from partial
    coverage or truncation notices, and include every row family in summary
    coverage. Export the completed-run and publication builders from
    `src/experiments/__init__.py` like the accounting/trade siblings.
  - Publication is programmatic after successful completion; no CLI producer,
    runner flag, or API write path.
  - Files above; tests `tests/unit/test_economic_inequality_publication.py`.
  - Logging: INFO `economic_inequality_published` with row counts; WARN skipped
    publication; ERROR `economic_inequality_publication_failed` safe code.
  - Depends on: 7, 10, 11.

- [x] Task 13: Add seven GET-only dual-gated routes
  - Create `src/api/economic_inequality_cursor.py` (purpose-bound codec, TTL
    900 s, `DiplomacyCursorCodec` alias) and
    `src/api/routes/economic_inequality.py` with
    `ECONOMIC_INEQUALITY_ROUTE_COUNT = 7` and:
    `GET /v1/simulations/{run_id}/economic-inequality`,
    `/dimensions`, `/possession`, `/access`, `/claims`, `/cohorts`,
    `/societies`.
  - Require `ApiCapability.SUBJECTIVE_DEBUG`; fail closed with
    `economic_inequality_disabled` when either setting is unset; reject corrupt
    stores with `economic_inequality_store_corrupt`; bind cursors to
    run/publication/digest/purpose/limit/`window_index`; default limit 100, max
    500, `window_index` <= 511.
  - Define route row filters explicitly: `/dimensions` returns all six
    dimensions, `/possession` only `resource_possession`, `/access` returns
    `{productive_tool_access, infrastructure_access, storage_access}`, and
    `/claims` returns `{credit_relationship,
    organizational_resource_control}`. Page order and cursor fingerprints bind
    the route's dimension set and `window_index`; a cursor from another window
    or dimension set is rejected 400.
  - Wire `_attach_economic_inequality_reader` in `src/api/app.py`, export the
    router in `src/api/routes/__init__.py`, and include it before the version
    router. Do not add `/v2`.
  - Files above; tests `tests/unit/test_economic_inequality_routes.py`,
    `tests/unit/test_economic_inequality_api_cursor.py`, and
    `tests/integration/test_economic_inequality_store_api.py`
    (`pytest.mark.integration`) covering store/API round-trip, dual-gate, and
    cursor mismatch.
  - Logging: INFO router ready/disabled; WARN cursor mismatch; ERROR store
    corruption; never log cursor keys or owner rows.
  - Depends on: 10, 11.

- [x] Task 14: Add the Research UI client and panel
  - Add `clients/research-ui/src/api/economicInequality.ts`,
    `src/views/EconomicInequalityPanel.svelte`, and panel tests. Register the
    view in `src/research/selection.ts` and `src/views/RunOverview.svelte`
    navigation, imports, and mount.
  - The panel renders summary, dimension distributions/indices, cohort rows,
    and society comparison rows read-only. It shows `unavailable` and
    `insufficient_samples` honestly and never computes a composite score.
  - No Godot files change.
  - Files above; tests `EconomicInequalityPanel.test.ts` and view/selection
    tests.
  - Logging: browser console only safe status tokens; no payload logging.
  - Depends on: 13.

### Phase 4: Experiment and End-to-End

- [x] Task 15: Register off-gate `economic_inequality@1`
  - Create `src/experiments/economic_inequality_scenario.py` with
    `ECONOMIC_INEQUALITY_EXPERIMENT_ID = "economic_inequality@1"` and three
    arms: `ei-baseline` (no economic channels), `ei-access`
    (`infrastructure_networks` + `collective_projects` + `durable_records` +
    `knowledge_repositories` + provenance), and `ei-full` (access plus
    `organizations`, `markets_credit`, `structured_commitments`, and
    `subjective_valuation`). The repository arm also enables
    `cultural_historical_memory` and the `cultural_feature_provenance` spec, as
    required by `durable_records` and `knowledge_repositories`. Use
    `runner-config-v56`, the exact v55 family keyset, and a finite stop horizon
    of at least 96 ticks.
  - Add `experiment_economic_inequality` to `src/experiments/catalog.py` and
    append the id to `OFF_GATE_MATRIX_EXPERIMENT_IDS`; never add it to
    `EXPERIMENT_A_V1_CONDITION_IDS`.
  - In the experiment tests, assert the id is in
    `OFF_GATE_MATRIX_EXPERIMENT_IDS`, absent from
    `EXPERIMENT_A_V1_CONDITION_IDS`, and that `ei-baseline` produces no
    `economic_inequality_*` metric input or snapshot field while `ei-access`
    and `ei-full` do.
  - Files above; tests `tests/unit/test_economic_inequality_experiment.py`,
    `tests/unit/test_economic_inequality_catalog.py`.
  - Logging: INFO `experiment_registered experiment_id=economic_inequality@1
    arms=3`; WARN invalid arm composition; ERROR setup codes.
  - Depends on: 1, 9, 12.

- [x] Task 16: Add in-process end-to-end coverage
  - Add `tests/unit/test_economic_inequality_end_to_end.py` using a real
    `WorldEngine` admission loop, real `Craft`, `Build`, `Store`, `Give`, and
    `Move` commands, real committed events, the real completed-run builder, a
    real finalized snapshot, a real filesystem store, and a real FastAPI read
    through `TestClient`.
  - Cover: possession/tool/storage/infrastructure access present; credit and
    organization-control claims separately present; cohort rows; society rows;
    snapshot round-trip; dual-gate success and 503 failure.
  - Add cross-seam regressions that mirror the accounting verification lessons:
    the real collector injects non-empty analysis and owner/control rows;
    paging spans at least three windows and rejects a cursor minted for another
    window; cumulative publication bytes are exercised across several
    publications; a corrupt store returns 500; and the summary's `truncated`
    and coverage reflect every row family.
  - Files above; tests as named.
  - Logging: capture-only assertions on safe tokens; no payload assertions in
    production logs.
  - Depends on: 9, 12, 13, 15.

- [x] Task 17: Add determinism, property bounds, and leakage coverage
  - Add `tests/unit/test_economic_inequality_determinism.py`,
    `_bounds.py`, and `_leakage.py`. Verify identical bytes across two runs with
    the same seed and hash seeds; Hypothesis properties for owner/event/row
    caps, monotone prefix stability, index ranges, milli shares, and
    `insufficient_samples`.
  - Assert objective rows never carry claim/org tokens or claim measures; claim
    rows never carry item ids, custody fields, or possession measures;
    analytical rows carry no owner ids; snapshot rows carry no owner ids.
  - Files above; tests as named.
  - Logging: no new production logs; tests assert bounded metadata only.
  - Depends on: 16.

### Phase 5: Invariants and Documentation

- [x] Task 18: Sweep context, catalog, and ownership pins
  - Update `tests/architecture/test_v4_context_registry.py` `DECLARED_ORDER` and
    `DECLARED_PREREQUISITES` to 15 contexts; update every hardcoded
    `v4-context-map-v2` to `v3`; update `_REQUIRED_CONTEXT_COUNT` assertions.
    Keep 12 flags / 8 owned / 4 unowned assertions unchanged. Defer the
    documentation heading-count and context-section assertions to Task 20 so
    the full architecture suite is not expected green until Task 19 lands.
  - Sweep `METRIC_FAMILY_COUNT` assertions from 220 to 228 in all ~89 test
    files, update append guards to hash the first 220 and assert positions
    220-227, and update metric-service log expectations from `catalog=220` to
    `catalog=228`.
  - Update 52 `docs/*.md` current-catalog footers to 228 while leaving
    historical counts (184, 208, 212, 216, 220 in feature history) untouched.
  - Add `tests/architecture/test_economic_inequality_boundaries.py` and
    `test_economic_inequality_invariants.py` asserting: analysis imports no
    API/persistence/experiments; no new flag, runner schema, command, event,
    write pair, `/v2` route, or migration; no `WorldState` import; no
    `economic_inequality` capability flag; 15/12/8/4 counts.
  - Files: test and docs sweeps above.
  - Logging: no new production logs.
  - Depends on: 1-17.

- [x] Task 19: Documentation via `$aif-docs`
  - Run the mandatory `$aif-docs` checkpoint. Create
    `docs/economic-inequality.md` covering overview, activation, six dimensions,
    measures, distributions and indices, cohort and society comparisons,
    legitimacy separation, bounds, read-only surfaces, non-goals, pins, and
    verification.
  - Update `README.md`, `.ai-factory/ARCHITECTURE.md`,
    `.ai-factory/DESCRIPTION.md`, `docs/architecture.md`,
    `docs/configuration.md`, `docs/analysis-metrics.md`,
    `docs/research-api.md`, `docs/v4-architecture.md`, and
    `docs/research-ui.md`; add cross-links in `docs/organizations.md`,
    `docs/credit-relationships.md`, and `docs/supply-chains.md`.
  - Record the V4-24 seam and `v4-context-map-v3` with 15 contexts, and state
    that V4-23 is not yet registered in `.ai-factory/ROADMAP.md`; do not edit
    the roadmap.
  - Files above.
  - Logging: documentation itself contains no runtime logging changes.
  - Depends on: 18.

- [x] Task 20: Add documentation pin and negative parity checks
  - Add `tests/unit/test_economic_inequality_docs.py` asserting the new page
    sections, 15-context and 228-family pins, seven route names, dual-gate
    token, six dimensions, eight families, no composite/wealth/ownership-truth
    claims, and negative non-goals.
  - Move the documentation heading-count assertion from Task 18 here: assert
    `docs/v4-architecture.md` contains exactly 15 context sections and the new
    `economic_inequality` section, and run
    `test_document_declares_every_context_and_section` only after Task 19.
  - Add parity checks that fail if docs claim a V4 capability flag, a new
    command/event, a Godot overlay, a CLI producer, a `/v2` route, or an
    objective legitimate-ownership metric.
  - Files above.
  - Logging: no new production logs.
  - Depends on: 19.

### Phase 6: Certification

- [x] Task 21: Required-gate verification certification
  - Run and record every lane in the Verification Receipt. Do not mark a lane
    green without its command and result; record `unexecuted` with the missing
    prerequisite for Compose/browser acceptance or any other env-gated lane.
  - Confirm `git status` has no `.ai-factory/ROADMAP.md` edit, no
    `alembic/versions/0018*` file, no `clients/godot-observer/` source change,
    no `/v2` route, and no new capability flag.
  - Confirm 43 commands, 73 observer semantic types, replay-v27/codec `v25`,
    Alembic `0017`, `/v1`, and `observer-protocol-v1`.
  - Files: `.ai-factory/plans/v4-24-economic-inequality.md` receipt only.
  - Logging: collect only metadata-safe summaries.
  - Depends on: 16-20.

## Commit Plan

- **Commit 1** (after tasks 1-5): `feat(analysis): add economic inequality contract and evidence`
- **Commit 2** (after tasks 6-9): `feat(analysis): compose economic inequality metrics and comparisons`
- **Commit 3** (after tasks 10-14): `feat(simulation): publish economic inequality snapshots and read surfaces`
- **Commit 4** (after tasks 15-17): `test: certify economic inequality experiment and end-to-end paths`
- **Commit 5** (after tasks 18-21): `test,docs: sweep V4 context and catalogue pins`

Commit checkpoints are suggestions only. Do not commit during `$aif-implement`
unless the user explicitly authorizes commits.

## Definition of Done

- V4-24 adds exactly one analysis-only context, `economic_inequality`; counts
  are 15 contexts / 12 flags / 8 owned / 4 unowned; the map is
  `v4-context-map-v3`; no capability flag, `runner-config-v57`, runner root
  field, per-agent key, command, event, observer semantic type, write pair,
  `/v2` route, or migration is added.
- Six dimensions are measured independently: resource possession, productive
  tool access, infrastructure access, storage access, credit relationships, and
  organizational resource control.
- Physical possession/access and ownership legitimacy are separate layers; no
  composite wealth, ownership, merit, poverty, or legitimacy score exists.
- Longitudinal windows are 32 ticks with at most 512 windows; each row carries a
  distribution and Gini/Theil/Atkinson/top-share where at least four samples
  exist, otherwise `insufficient_samples`.
- Cohorts are generation cohorts; societies are detached `msoc-` candidates;
  overlap is legal; no ranking or best/worst label exists.
- Eight metric families append exactly at positions 220-227; the first 220 ids,
  order, versions, and value keys are unchanged; every active pin and docs
  footer is swept to 228.
- Analysis activates only with committed events plus an economic channel;
  otherwise no metric input, no snapshot field, and no off-path change.
- Evidence comes from committed events only; no `WorldState`, runtime, store, or
  API object is read.
- `economic-inequality-snapshot-v1` round-trips canonically with no wall-clock
  field; `economic-inequality-store-v1` is atomic, quota-bounded, idempotent,
  and corruption-safe.
- Seven GET-only dual-gated routes fail closed with
  `economic_inequality_disabled`, default limit 100, max 500, `window_index` <=
  511; the Research UI panel is read-only; no new Godot overlay exists.
- Publication is programmatic and post-completion; no CLI producer or runner
  flag is added.
- Off-gate `economic_inequality@1` is registered with three arms and is absent
  from the V1 A-E gate.
- Commands stay 43; observer semantics stay 73; replay-v27/codec `v25` stay the
  maximum; Alembic stays `0017`; `/v1` and `observer-protocol-v1` stay.
- The in-process E2E uses real admission, real commands, real events, a real
  snapshot, a real store, and a real API read.
- Determinism across hash seeds, cap-bound properties, and leakage guards pass;
  cross-seam coverage exercises collector -> analysis, multi-window paging,
  cumulative publication bytes, corrupt-store handling, and dual-gate failure.
- Docs cover the new page plus README, ARCHITECTURE, DESCRIPTION,
  `docs/architecture.md`, `docs/configuration.md`, `docs/analysis-metrics.md`,
  `docs/research-api.md`, `docs/v4-architecture.md`, `docs/research-ui.md`, and
  cross-links in `docs/organizations.md`, `docs/credit-relationships.md`, and
  `docs/supply-chains.md`, with positive and negative parity checks.
- Required gates are certified or explicitly `unexecuted`; the roadmap remains
  owned by `$aif-roadmap`, which must register V4-23 and V4-24 later.

## Verification Receipt

Filled by Task 21. No lane is green until its command and result are recorded
here.

| Lane | Command | Result | Prerequisite / note |
| --- | --- | --- | --- |
| Unit + architecture correctness | `uv run pytest tests/unit tests/architecture -q` | passed: 11622 passed in 720.57s |  |
| Focused economic-inequality suites | `uv run pytest tests/unit/test_economic_inequality_*.py tests/unit/test_inequality_indices.py tests/architecture/test_economic_inequality_*.py tests/integration/test_economic_inequality_store_api.py -q` | passed: 171 passed, 1 deselected |  |
| Python coverage (focused) | `uv run pytest tests/unit/test_economic_inequality_*.py tests/unit/test_inequality_indices.py tests/architecture/test_economic_inequality_*.py -q --cov=src --cov-report=term` | passed: 171 passed; whole-`src` total 21% (focused lane) |  |
| Python coverage (full lane) | `uv run pytest tests/unit tests/architecture -q --cov=src --cov-report=term` | unexecuted: timed out at 1800s with no receipt; non-coverage full lane is green | rerun with a longer timeout |
| Static: Ruff | `uv run ruff check src tests` | passed: All checks passed |  |
| Static: mypy | `uv run mypy src tests` | passed: Success, 2711 files |  |
| Static: import boundaries | `uv run lint-imports` | passed: 25 kept, 0 broken |  |
| Integration (non-scale) | `uv run pytest tests/integration -m "not scale" -q` | passed: 57 passed, 60 skipped, 5 deselected |  |
| Economic-inequality store/API integration | `uv run pytest tests/integration/test_economic_inequality_store_api.py -q -m integration` | passed: 1 passed |  |
| Compose config | `docker compose config` | passed |  |
| Research UI tests | `cd clients/research-ui && ./node_modules/.bin/vitest run` | passed: 316 tests, 67 files |  |
| Research UI types | `cd clients/research-ui && ./node_modules/.bin/svelte-check --tsconfig ./tsconfig.app.json` | passed: 0 errors, 0 warnings |  |
| Godot regression | `GODOT_BIN=~/.cache/palimpsest-godot/Godot_v4.7.2-stable_linux.x86_64 "$GODOT_BIN" --headless --path clients/godot-observer --script res://tests/run_protocol.gd` | passed: godot_protocol_tests failed=0 | existing suite only; no client change |
| Compose/browser acceptance | attested image + headed browser harness | unexecuted | requires attested image |
| Benchmark regression (non-scale) | `PALIMPSEST_V4_SCALE_IDS=100000 uv run pytest tests/benchmarks -m "not scale" -q` | passed: 1 passed, 20 deselected |  |

`git status` must confirm no `.ai-factory/ROADMAP.md` edit from this plan, no
`alembic/versions/0018*` file, no `clients/godot-observer/` source change, no
`/v2` route, and no new V4 capability flag. The new context registration,
analysis modules, snapshot/store, seven routes, Research UI panel, eight metric
families, docs, and off-gate experiment are the only V4-24 surfaces changed.
