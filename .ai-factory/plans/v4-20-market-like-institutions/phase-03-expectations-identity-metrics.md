# Phase 3: Expectations, Identity, Metrics, and Pins

Plan: [index.md](index.md)
Tasks: 8-12
Depends on: Phase 2 / Tasks 5-7

## Objective

Join detached owner expectations, role claims, and record anchors to the
objective venue layer; classify researcher-only expectation alignment; mint
market identities and forward-only lineage including empty windows; compose one
bounded `MarketInstitutionsAnalysis`; append four metric families to 208; and
sweep every ownership and catalog pin in the same change.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/analysis/trade_networks_identity.py` | overlap (102-108), link (126-244), empty windows (63-95) | Lineage algorithm to mirror |
| `src/analysis/trade_networks_analysis.py` | `TradeNetworksAnalysis` (65-69), harvest (154-281) | Composition and coverage aggregation |
| `src/analysis/trade_networks_layers.py` | `TradeLayerView` (27-49), separation (72-94) | Layer projection |
| `src/analysis/trade_networks_metrics.py` | `_document` (90-139), computes (163-544), assemble (547-574) | Metric document assembly |
| `src/analysis/specifications.py` | `METRIC_FAMILY_COUNT` (53), enum (75+), trade ids (270-275), key constants (8723-8808), `_BUILDERS` (9353+), validation (9579-9610) | Catalog append mechanics |
| `src/analysis/metric_service.py` | `MetricComputationInputs` (300-390), trade block (2459-2501) | Analysis-to-document dispatch |
| `src/simulation/market_institutions_export.py` | created in Task 13 | Token-only owner export rows mapped into Task 8 analysis inputs |
| `tests/architecture/test_v4_architecture_invariants.py` | `METRIC_FAMILY_COUNT == 204` (140), owned literal sets (182-216) | Ownership/catalog pins |
| `tests/unit/test_supply_chain_pins.py` | `204` scan (27-33), owned seven (50-53) | Suite-wide meta-pins to extend |
| `tests/unit/test_runner_config_v56.py` | unowned parameterization (249-270) | `markets_credit` fixture must move to `science` |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/analysis/market_institutions_expectations.py` | create | Owner join, alignment, roles, records |
| `src/analysis/market_institutions_identity.py` | create | Market identity and lineage |
| `src/analysis/market_institutions_layers.py` | create | Four-layer projection and leakage guard |
| `src/analysis/market_institutions_analysis.py` | create | Bounded harvest object |
| `src/analysis/market_institutions_metrics.py` | create | Four metric computes and assembler |
| `src/analysis/specifications.py` | modify | Four family ids, key constants, builders, count 208 |
| `src/analysis/metric_service.py` | modify | Input field and dispatch block |
| `src/analysis/__init__.py` | modify | Facade exports |
| `tests/**` | modify | 204 → 208 sweep and ownership fixture repoint |

## Task 8: Join detached expectations, roles, records, and alignment

### Intent

Add the owner-scoped analytical lane without fabricating beliefs: when no owner
rows exist the coverage is `missing` and every owner-derived tuple is empty.
Researcher-only alignment is descriptive and never reaches cognition.

### Implementation Steps

1. Define analysis-owned input rows in `src/analysis/market_institutions_rows.py`:
   `MarketOwnerExpectationInput(owner_token, venue_token, expectation, cadence,
   interval_ticks, phase_tick, schedule_window_index, confidence_milli,
   evidence_count, first_tick, last_tick)`,
   `MarketOwnerRoleInput(owner_token, venue_token, role_kind, role_basis,
   recognized, actor_token, first_tick, last_tick)`, and
   `MarketOwnerRecordInput(owner_token, venue_token, record_kind, anchor_token,
   first_tick, last_tick)`. These are the analysis boundary types; Task 13 maps
   `simulation.market_institutions_export.MarketOwnerExportRow` values into them
   so analysis never imports the export module's storage shape.
2. Create `src/analysis/market_institutions_expectations.py`:
   - `join_expectations(expectation_inputs, *, venues, window_end, policy)`
     emits one
     `MarketExpectationRow` per `(window_index, venue_id, owner_token)` with
     expectation, cadence, interval/phase/window, confidence, evidence count,
     and alignment;
   - alignment: enumerate the windows from the venue's first active window
     through `window_end`; a window is expected when the cadence predicts it:
     `recurring_interval` → the window contains at least one tick `t` in
     `[window_start, window_end]` with
     `(t - phase_tick) % interval_ticks == 0`; `periodic_window` → only the
     named `schedule_window_index`; `single_occurrence` and `unknown` → not
     applicable. Count expected windows and those with a gathering;
     `alignment_milli = observed * 1000 // expected` (0 when expected is 0);
     `consistent` at `>= alignment_high_milli`, `inconsistent` at
     `< alignment_low_milli`, `unresolved` otherwise; `not_applicable` when
     cadence is `unknown` or `single_occurrence`. Alignment is venue-level and
     repeated identically on each window row for the same owner/venue;
   - `join_roles(role_inputs, *, venues, participation, policy)` emits
     `MarketRoleRow(venue_id, window_index, actor_token, role_kind, role_basis,
     recognized, exchange_count, counterparty_count, active_window_count,
     coverage)`; `recognized` is true only for `office`/`organization` basis;
     broker rows require `broker_like=True` in participation;
   - `join_records(record_inputs, *, venues, policy)` emits
     `MarketRecordRow(venue_id, window_index, record_kind, anchor_token,
     owner_row_count, coverage)`; anchors are copied opaque tokens, never
     dereferenced;
   - per-family caps use the Task 5 policy; truncation adds the matching notice
     and rewrites rows to `partial`;
   - `expectation_coverage`, `role_coverage`, and `record_coverage` are
     `missing` when the corresponding row family is absent, `partial` on any
     notice/unresolved row, else `complete`.
3. Add `join_market_owner_rows(*, expectation_inputs, role_inputs,
   record_inputs, venues, participation, window_end, policy)` returning all
   three row tuples plus coverage and notices in one deterministic call.
4. Reject foreign row types with `market_institutions_invalid_input`.
5. Export the join functions and rows through `analysis/__init__.py`.

### Required Interfaces and Contracts

- An owner row never contains an objective event token; a role row never
  contains an item token; a record row never contains payload text.
- `owner_token` is that owner's export token; one owner may contribute several
  expectation rows per venue only across different windows.
- `recognized=False` for every `observed_participation` and `claimed` basis,
  regardless of participation counts.
- Missing owner rows never produce a row with default values; they produce
  empty tuples and `missing` coverage.

### Requirement Evidence

- Original Request: "expectations form"; "records/roles emerge"; "brokers if
  emergent"; "exchange records".
- `src/experiments/migration_displacement_harvest.py:413-435` — detached owner
  ledger export composition.
- `src/simulation/migration_displacement_export.py:311-342` — token-only owner
  projection and foreign-owner rejection.

### Error Handling and Logging

- DEBUG: `market_owner_rows_joined expectations=<n> roles=<n> records=<n>
  coverage=<state>`.
- WARN: `market_expectation_rows_truncated`, `market_role_rows_truncated`,
  `market_record_rows_truncated` with counts only.
- Never log owner tokens, anchors, or role actor tokens.

### Tests

- `tests/unit/test_market_institutions_expectations.py`: expectation join;
  cadence prediction for interval 1, 32, 33 and phase boundaries; alignment
  boundaries; expected-venue counting; recognized-role
  matrix; broker gating; record anchors; missing coverage; caps; foreign row
  rejection; no objective tokens in owner rows.

### Acceptance Criteria

- No owner rows → `expectation_coverage=missing`, `role_coverage=missing`,
  `record_coverage=missing`, and three empty tuples.
- A `strong` expectation with schedule `recurring_interval` matching three of
  four observed windows yields `alignment_milli=750` and `consistent`.

### Verification

- `uv run pytest tests/unit/test_market_institutions_expectations.py -q`
- Expected result: all pass.

## Task 9: Mint market identities and forward-only lineage

### Intent

Give each per-window market cluster a content-addressed `mktc-` identity and
link clusters across every consecutive window, including empty windows, with
the same forward-only semantics used by V4-18 networks.

### Implementation Steps

1. Create `src/analysis/market_institutions_identity.py`:
   - `mint_market_token(venue_tokens)` delegates to Task 5's
     `market_candidate_token`;
   - `group_markets_by_window(candidates, *, first_window, last_window)` returns
     a tuple per window, materializing `()` for missing windows;
   - `link_market_lineage(previous, current, *, policy, previous_window_index,
     current_window_index)` validates single-window inputs, duplicate market
     tokens, and non-decreasing windows;
   - overlap is `intersection * 1000 // min(len(left), len(right))` over venue-id
     sets, with both empty = `1000` and one empty = `0`; link at
     `>= lineage_overlap_milli`;
   - relation precedence: `split` when a previous market has two or more
     successors, `merge` when a current market has two or more predecessors,
     `continued` when venue sets are equal, else `transformed`;
   - unlinked previous → `dissolved`; unlinked current → `emerged`; parents are
     never rewritten;
   - emit `MarketLineageRow(window_index, market_token, venue_ids,
     party_count, status, previous_market_tokens, next_market_tokens, rerouted,
     sustained, coverage)` with sorted unique token tuples and ticks bounded by
     the two windows; `party_count` is the number of distinct party tokens
     across the cluster's venue participant rows in the current window.
2. Add `link_market_series(grouped, *, policy)` iterating
   `itertools.pairwise(range(first, last + 1))` and returning bounded lineage
   rows; cap `max_lineage_edges`, retain the sorted prefix, add
   `market_institutions_lineage_truncated`, set `lineage_coverage=partial`.
3. Reject reversed windows, mixed-window batches, and duplicate tokens with
   `market_institutions_invalid_identity`.
4. Export the functions through `analysis/__init__.py`.

### Required Interfaces and Contracts

- A venue id set is the only identity material; party counts, exchange counts,
  and owner rows never affect identity.
- `rerouted = status == transformed`; `sustained = status in
  {continued, transformed}`.
- A gap of one or more empty windows produces `dissolved` then `emerged`; it
  never produces a silent `continued`.
- Lineage rows are forward-only; a later window never mutates an earlier row.

### Requirement Evidence

- Original Request: "market-like institution persists".
- `src/analysis/trade_networks_identity.py:63-244` — exact overlap, precedence,
  empty-window and cap behavior.

### Error Handling and Logging

- DEBUG: `market_lineage_linked windows=<n> edges=<n>`.
- WARN: `market_lineage_truncated edges=<n>`.
- Never log venue ids or market tokens.

### Tests

- `tests/unit/test_market_institutions_identity.py`: content-addressed ids;
  overlap boundaries 0/499/500/1000; continued/transformed/split/merge/
  dissolved/emerged; empty-window gap; duplicate and reversed rejection; cap;
  parent immutability.

### Acceptance Criteria

- Two identical venue sets in consecutive windows yield `continued`.
- A shared venue set that loses one of two venues with overlap `500` yields
  `transformed`, not `dissolved`.

### Verification

- `uv run pytest tests/unit/test_market_institutions_identity.py -q`
- Expected result: all pass.

## Task 10: Compose the bounded `MarketInstitutionsAnalysis` harvest

### Intent

Provide one deterministic analysis object that later metric, snapshot, and
publication tasks consume without re-reading events or choosing thresholds.

### Implementation Steps

1. Create `src/analysis/market_institutions_analysis.py` with
   `MarketInstitutionsAnalysis` (frozen, slots): `window_tick`,
   `policy_version`, `evidence_coverage`, `expectation_coverage`,
   `role_coverage`, `record_coverage`, `lineage_coverage`, `coverage`,
   `venues`, `gatherings`, `participation`, `markets`, `expectations`, `roles`,
   `records`, `lineage`, `notices`, `exchange_count`, `attempt_count`.
2. Add `harvest_market_institutions_analysis(*, committed_events,
   expectation_inputs=(), role_inputs=(), record_inputs=(), policy=None,
   window_end=None) -> MarketInstitutionsAnalysis`:
   - resolve policy or `default_market_institutions_analysis_policy()`;
   - extract evidence (Task 6); derive `window_end` from the last exchange tick
     when not supplied, and reject a supplied value below the last tick;
   - detect gatherings/venues/participation/markets (Task 7);
   - join `expectation_inputs`, `role_inputs`, and `record_inputs` with
     `window_end` (Task 8); no venue status is rewritten;
   - group markets per window and link lineage from the first exchange window to
     `window_end` (Task 9);
   - aggregate coverage: `missing` when evidence is missing and all owner lanes
     are missing; `partial` when any lane is `partial`/`missing` or any notice
     exists; else `complete`;
   - sort every row tuple by its documented key and expose counts equal to
     tuple lengths.
3. Add `empty_market_institutions_analysis(window_tick=0)` returning missing
   coverage and empty tuples.
4. Add `market_institutions_analysis_digest(analysis)` over canonical rows for
   determinism tests.
5. Create `src/analysis/market_institutions_layers.py` with
   `MarketLayerView(objective, owner, analytical, comparison)` and
   `project_market_layers(analysis)`; call Task 7's separation assertion during
   projection.
6. Export `MarketInstitutionsAnalysis`, `empty_market_institutions_analysis`,
   `harvest_market_institutions_analysis`, `MarketInstitutionsAnalysisPolicy`,
   `default_market_institutions_analysis_policy`, and the row classes consumed
   by experiments/publication through `analysis/__init__.py`. Keep
   `MarketLayerView`, `project_market_layers`, and the join functions internal
   to their modules, matching the V4-18 facade boundary.

### Required Interfaces and Contracts

- The harvest never reads `WorldState`, `WorldEngine`, an agent runtime, a store,
   or an API object.
- `window_tick` is the last tick covered by the analysis; it is never a
  wall-clock value.
- Repeated calls with equal inputs and policy produce byte-identical tuple
  ordering.
- `empty_market_institutions_analysis` is the only zero-value constructor; no
  detector fabricates rows to satisfy a metric.

### Requirement Evidence

- Original Request: "Detect market-like persistence analytically."
- `src/analysis/trade_networks_analysis.py:154-281` — harvest composition and
  coverage aggregation.

### Error Handling and Logging

- DEBUG: `market_analysis_composed windows=<n> venues=<n> markets=<n>
  coverage=<state>`.
- WARN: `market_analysis_partial notices=<n>`.
- ERROR: `market_analysis_rejected reason_code=<code>`.
- Never log locations, actors, owner rows, or anchors.

### Tests

- `tests/unit/test_market_institutions_analysis.py`: empty analysis; full
  composition; window_end derivation/rejection; deterministic ordering; coverage
  aggregation matrix; layer projection and leak; digest stability; no
  forbidden keys.

### Acceptance Criteria

- The harvest over a three-window stream yields non-empty venues, participation,
  markets, and lineage, and `coverage` is `complete` when all lanes are
  complete.
- Supplying no owner rows leaves the objective rows unchanged and marks only
  owner lanes `missing`.

### Verification

- `uv run pytest tests/unit/test_market_institutions_analysis.py -q`
- Expected result: all pass.

## Task 11: Add four market metric families to 208

### Intent

Append four descriptive families that describe venue recurrence, persistence,
expectation structure, and role structure, while keeping the first 204 families
byte-identical.

### Implementation Steps

1. In `src/analysis/specifications.py`:
   - add enum members `MARKET_VENUE_RECURRENCE = "market_venue_recurrence"`,
     `MARKET_VENUE_PERSISTENCE = "market_venue_persistence"`,
     `MARKET_EXPECTATION_STRUCTURE = "market_expectation_structure"`,
     `MARKET_ROLE_STRUCTURE = "market_role_structure"`;
   - set `METRIC_FAMILY_COUNT = 208`;
   - add key constants and `_spec_*` builders after the supply-chain builders;
   - append the four builders to `_BUILDERS` in the same order.
2. Lock exact value keys:
   - `MARKET_VENUE_RECURRENCE_KEYS`: `window_tick`, `venue_count`,
     `gathering_count`, `recurring_venue_count`, `persistent_venue_count`,
     `mean_recurrence_milli`, `max_recurrence_milli`,
     `multi_party_gathering_count`, `coverage`.
   - `MARKET_VENUE_PERSISTENCE_KEYS`: `window_tick`, `venue_count`,
     `active_venue_count`, `emerged_count`, `continued_count`,
     `transformed_count`, `split_count`, `merge_count`, `dissolved_count`,
     `rerouted_count`, `sustained_market_count`, `coverage`.
   - `MARKET_EXPECTATION_STRUCTURE_KEYS`: `window_tick`,
     `expectation_row_count`, `expected_venue_count`, `scheduled_venue_count`,
     `record_anchor_count`, `consistent_count`, `unresolved_count`,
     `inconsistent_count`, `not_applicable_count`, `expectation_coverage`,
     `record_coverage`.
   - `MARKET_ROLE_STRUCTURE_KEYS`: `window_tick`, `role_row_count`,
     `broker_like_count`, `recognized_role_count`, `claimed_role_count`,
     `venue_with_role_count`, `mean_counterparty_count_milli`,
     `role_coverage`.
3. Create `src/analysis/market_institutions_metrics.py` with
   `assemble_market_institution_metrics(analysis, *, run_id, input_revision)`
   and four compute functions. Each:
   - rejects a foreign analysis type with
     `market_institutions_metrics_invalid_analysis`;
   - maps coverage to `present`/`partial`/`unknown` and short-circuits unknown to
     an empty-values document;
   - uses integer `_milli` ratios and `quantize_float` only for
     `MetricCoverage.ratio`;
   - sets provenance `source_kind="market_institutions_analysis"`,
     `source_ids=(run_id, input_revision, policy_version,
     "market-institutions")`, and `notes_code="detached_market_analysis"`.
4. In `src/analysis/metric_service.py`:
   - import `MarketInstitutionsAnalysis` and the four computes;
   - add `market_institutions_analysis: MarketInstitutionsAnalysis | None = None`
     to `MetricComputationInputs`;
   - append a block after the supply-chain block that emits the four documents
     with `_safe(...)` and logs
     `market_institutions_metrics_emitted families=4`.
5. Import `assemble_market_institution_metrics` directly in
   `src/analysis/metric_service.py`; do not add it to the `analysis` facade,
   matching V4-18's internal-assembler boundary.

### Required Interfaces and Contracts

- Families are appended after the supply-chain block; the first 204 ids, order,
  versions, and value keys do not change.
- Only `market_venue_persistence` may report `emerged`/`continued`/`transformed`/
  `split`/`merge`/`dissolved`; no family reports a composite persistence score.
- `expectation_coverage` and `record_coverage` are strings from the closed
  coverage enum, never numeric.
- No family key contains `price`, `money`, `currency`, `score`, `ranking`,
  `severity`, `recommendation`, `allocation`, or `quota`.

### Requirement Evidence

- Original Request: "Detect market-like persistence analytically."
- `src/analysis/specifications.py:53,270-275,8723-8808,9353-9610` — append
  mechanics and key constants.
- `src/analysis/trade_networks_metrics.py:90-139,547-574` — document assembly.

### Error Handling and Logging

- INFO: `market_institutions_metrics_emitted families=4 catalog=208`.
- DEBUG: `market_institutions_metrics_disabled` when the analysis input is
  absent.
- ERROR: `market_institutions_metrics_rejected
  reason_code=invalid_analysis`; never log row values.

### Tests

- `tests/unit/test_market_institutions_metrics.py`: four documents with exact
  keys; unknown/partial/present mapping; ratio/count boundaries; no forbidden
  keys; deterministic assembly order.
- `tests/unit/test_market_institutions_catalog.py`: `METRIC_FAMILY_COUNT == 208`;
  first 204 specs unchanged by digest; market families at indices 204-207 in the
  locked order; `validate_metric_catalog()` passes.

### Acceptance Criteria

- `all_metric_specifications()[204:208]` equals the four market families in the
  locked order.
- A SHA-256 digest over the first 204 specifications matches the pre-change
  digest captured in the test.

### Verification

- `uv run pytest tests/unit/test_market_institutions_metrics.py tests/unit/test_market_institutions_catalog.py -q`
- Expected result: all pass.

## Task 12: Sweep suite-wide ownership and catalog pins

### Intent

Make the repository truthful in one change: 208 families, eight owned V4 flags,
and unowned-flag fixtures that no longer use `markets_credit`.

### Implementation Steps

1. Replace every test pin `== 204` with `== 208` and every literal metric-count
   assertion of 204 with 208. At plan time `rg -l '\b204\b' tests -g '*.py'`
   returns 84 files; the sweep must leave no `== 204` in `tests/` and no
   `METRIC_FAMILY_COUNT == 204`.
2. Update `tests/architecture/test_v3_baseline_inventory.py` metric family count
   to 208.
3. Fix slice pins that assume the supply-chain block is the final block:
   `tests/unit/test_trade_networks_catalog.py:46-61` must keep
   `specs[:198]`, change `specs[198:]` to `specs[198:204]` for the six
   supply-chain families, and add a `specs[204:208]` market block assertion.
   The digest of the first 198 specifications remains unchanged.
4. Update `tests/architecture/test_v4_architecture_invariants.py`:
   - line 140 `METRIC_FAMILY_COUNT == 208`;
   - owned literal sets at 182-197 and 206-216 add `markets_credit`;
   - keep context/flag counts at 14/12.
5. Update `tests/unit/test_supply_chain_pins.py`:
   - rename `test_catalog_pins_are_204` to `test_catalog_pins_are_208` and scan
     for stale `== 204`;
   - `test_owned_flag_count_is_seven` becomes
     `test_owned_flag_count_is_eight`, asserts 8, and asserts both
     `supply_chains` and `markets_credit` are owned;
   - add `test_no_test_expects_markets_credit_unimplemented` with the same
     window rule used for `supply_chains`.
6. Extend `tests/unit/test_v4_scaffolding_gate.py:150-151`: add
   `markets_credit` to the owned-flag construction parametrization and assert it
   constructs on v56 while `v4_scaffolding_profile` still rejects the enabled
   flag.
7. Repoint unowned-flag fixtures from `markets_credit` to `science`:
   `tests/unit/test_runner_config_v56.py:249-270`,
   `tests/unit/test_v4_scaffolding_gate.py:40-60,120-150`,
   `tests/unit/test_diplomacy_treaty_config.py:135`, and any other fixture whose
   sole intent is `capability_unimplemented`. Leave all-flag name lists (for
   example `tests/unit/test_godot_protocol_mirror.py:83`) unchanged.
8. Update `src/simulation/compatibility.py` prose to "eight owned / four
   unowned" and list V4-20.
9. Run a stale-pin audit:
   `rg -n "== 204\b|METRIC_FAMILY_COUNT == 204" tests` returns no matches and
   `rg -n "markets_credit=True" tests` returns only owned-path tests.

### Required Interfaces and Contracts

- Counts after the sweep: 14 contexts, 12 flags, 8 owned, 4 unowned, 208 metric
  families, 43 commands, 73 observer semantic types, replay-v27/codec `v25`,
  Alembic `0017`.
- No test may assert that `markets_credit` is unimplemented.
- Historical prose inside old docs pages is not a test pin and is handled in
  Phase 8.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "Versioned Extension Contract" — current pins and
  capability ownership.
- `tests/unit/test_supply_chain_pins.py:1-53` — suite-wide pin pattern.
- `src/analysis/specifications.py:53` and `src/simulation/compatibility.py:155-165`
  — single sources of truth.

### Error Handling and Logging

- No runtime logging; this is a test/source sweep.
- If a stale `== 204` remains, the new meta-pin fails with the offending path
  list, not a silent pass.

### Tests

- `tests/unit/test_market_institutions_pins.py`: catalog 208; owned 8; no
  stale 204; no `markets_credit` unimplemented expectation; no `runner-config-v57`
  in `src/`.
- `tests/architecture/test_v4_architecture_invariants.py` (updated).
- `tests/unit/test_supply_chain_pins.py` (updated).

### Acceptance Criteria

- `rg -n "== 204\b" tests` returns no matches.
- `V4_OWNED_CAPABILITY_FLAGS` equals the eight owned flags.
- Enabling `markets_credit` no longer raises `capability_unimplemented`.

### Verification

- `uv run pytest tests/unit/test_market_institutions_pins.py tests/unit/test_supply_chain_pins.py tests/architecture/test_v4_architecture_invariants.py -q`
- Expected result: all pass.

## Phase Risks and Mitigations

- Risk: an incomplete 204 sweep leaves one stale assertion that only fails in a
  different lane. Mitigation: the new stale-204 scanner plus a full
  `rg`-verified sweep.
- Risk: ownership fixtures silently start testing the wrong flag.
  Mitigation: Task 12 names the exact files and adds a negative test that no test
  expects `markets_credit` unimplemented.
- Risk: owner alignment leaks objective truth into cognition. Mitigation:
  alignment exists only in analysis rows and the layer guard forbids objective
  event tokens in owner rows and owner tokens in objective rows.

## Phase Completion Checklist

- Every Task 8-12 acceptance criterion is verified.
- Four metric families append to exactly 208 with the first 204 unchanged.
- Eight V4 flags are owned; four remain unowned.
- `index.md` task checkboxes are updated immediately after verified completion.
