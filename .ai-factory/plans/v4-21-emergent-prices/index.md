<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: Emergent Prices

Mode: ultra
Branch: main
Created: 2026-11-11
Plan identifier: `v4-21-emergent-prices`

## Original Request

v4-21 prices and exchange units

Naming requirement:

Use `v4-21-emergent-prices`.

Build on V3 medium-of-exchange detection.

Allow agents to develop subjective price expectations.

No global price table.

Represent:

agent valuation  
observed past exchanges  
quoted offers  
reference units  
confidence

Support analytical price distributions rather than one canonical price.

Measure convergence/divergence between markets.

## Settings

- Testing: yes; full strategy. Unit, architecture, determinism, integration,
  Compose/browser, Godot regression (existing suites only), Research UI,
  benchmark regression, and static gates, with coverage enabled for Python
  lanes.
- Logging: verbose, metadata-only. Bounded DEBUG ledger/evidence/distribution
  counts and selected status tokens, INFO activation/publication/build
  milestones, WARN truncation/partial coverage/malformed frames/unresolved
  anchors, ERROR safe codes. `PALIMPSEST_LOG_LEVEL` controls operational
  verbosity. Never log owner valuations, item kinds, unit tokens, quoted ratios,
  counterparty sets, confidence values, owner tokens, record anchors, cursor
  keys, credentials, tokens, DSNs, memories, embeddings, or payload surrogates.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 23.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints are suggestions, not authorization to
  commit during planning or implementation unless the user explicitly asks.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-21-emergent-prices`; the ultra bundle directory is
  `.ai-factory/plans/v4-21-emergent-prices/`, phase files use
  `phase-NN-<slug>.md`, and `index.md` is the canonical entrypoint. Python and
  artifact tokens use `emergent_prices` / `emergent-prices-*` because
  identifiers cannot contain hyphens; the human-readable feature name is
  "emergent prices".
- Research source: `.ai-factory/RESEARCH.md` and `.ai-factory/research/` do not
  exist; no external research conclusions are invented.
- Execution: plan only in this invocation. No implementation, commit, roadmap
  edit, or branch creation occurs while planning.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"
Rationale: V4-21 deepens the already-owned `markets_credit` V4 context and the
V3-18/V3-19 valuation/medium-of-exchange seams into owner-scoped price
expectations with detached analytical distributions, adding no new V4 context,
flag slot, runner schema, command, event, money, credit, or global price table.
This plan does not edit or close the roadmap; `$aif-roadmap` must register V4-21
in M8, re-confirm V4-17, V4-18, V4-19, and V4-20, and record that eight V4 flags
remain owned and four remain unowned.

## Requirements Reconciliation

Authority: the Original Request defines scope; `.ai-factory/ARCHITECTURE.md`
("Key Principles", "Versioned Extension Contract", V4-01 through V4-20 seams) and
`.ai-factory/RULES.md` constrain every edit; `.ai-factory/DESCRIPTION.md` and
`.ai-factory/ROADMAP.md` describe current state; the source paths below define the
concrete contracts. No requirement source is edited to create this plan; the
landing in Task 23 records the implemented seam in the descriptive project
documents, while the roadmap remains owned by `$aif-roadmap`.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-21 deepens the already-owned `markets_credit` context; contexts stay 14, flags 12, owned 8, unowned 4; no new context, flag slot, `runner-config-v57`, root field, or per-agent runner key | Original Request; `src/simulation/v4_architecture.py:56,212-228`; `src/simulation/runner_models.py:328-339,1128-1179` | Task 3/19/22/25 |
| `markets_credit` stays `OWNER_SCOPED` with owners `("agents.cognition","simulation")`, `uses_existing_events=True`, and prerequisites `SUPPLY_CHAINS`/`ORGANIZATIONS`; prerequisites are planning order, never a runtime gate | Original Request; `v4_architecture.py:212-228` | Task 1/22/25 |
| Price cognition is active only when `markets_credit` is enabled **and** the V3-18 `subjective_valuation` spec is present; otherwise no ledger, no notices, and V4-20 behavior is unchanged | Original Request "Build on V3 medium-of-exchange detection"; `src/simulation/runner_models.py:5198-5265`; `src/agents/cognition/loop.py:1553-1578,2139-2230` | Task 3/19/20 |
| V3-19 `resource_exchange_profile` and `acceptance_memory` supply observed-medium unit candidates; they remain descriptive and never name money or a currency | Original Request; `src/simulation/runner_models.py:5273-5352`; `src/world/resource_profile.py:16-48`; `src/agents/cognition/acceptance_memory.py:24-226`; `docs/analysis-metrics.md:113` | Task 2/8/22 |
| Exchange primitives stay `NegotiateExchange`, `ExchangeProposed`, `ExchangeWithdrawn`, and `ExchangeCompleted`; no field, admission rule, quantity, price, or unit is added | Original Request "No global price table"; `src/world/actions.py:882-908`; `src/world/events.py:2456-2564`; `src/world/_rules.py:5954-6070` | Task 1/2/6/20/22 |
| Owner representation is one bounded `EmergentPriceLedger`: item-kind token, unit kind/source, owner valuation reservation, observed exchange ratios, quoted offers, expectation, confidence, counts, and notices; no item ids, inventories, peer state, or world state | Original Request; `src/agents/cognition/subjective_value.py:23-128`; `src/agents/cognition/market_institutions.py:306-749,1265-1453` | Task 1/2/3/22 |
| Quoted offers and expectations travel as bounded `prc_v1` frames inside existing `Talk`/`Tell`; no new speech command, offer field, or V3 convention situation is added | Original Request "quoted offers"; `src/agents/cognition/market_institutions_communication.py:36-283`; `src/agents/cognition/deliberation.py:1393-1405` | Task 4/22 |
| The only behavioural effect is one optional `prc_v1` relation attached to an already-selected `Talk`/`Tell`; no command is created or replaced and exchange admission never reads expectations | Original Request; `src/world/_rules.py:5954-6028`; `.ai-factory/ARCHITECTURE.md` "Anti-Patterns" | Task 4/20/22 |
| Analysis evidence is committed exchange events plus detached owner export rows; venue attribution uses `occurrence.origin_location_id`; no `WorldState`, runtime, store, API object, or peer ledger is read | Original Request; `src/world/events.py:344-390,4327-4413`; `src/analysis/trade_networks_events.py:172-176,477` | Task 5/6/10/20/22 |
| A price ratio exists only when each side of an exchange is homogeneous in one distinct kind; heterogeneous, same-kind, and out-of-range bundles are excluded, never averaged into a canonical price; completed and quoted evidence form separate distributions | Original Request "Support analytical price distributions rather than one canonical price"; `src/analysis/exchange_functions.py:203-238`; `src/analysis/trade_networks_detection.py:269-319` | Task 6/7/8/21 |
| Venue distributions report `sample_count`, five quantiles, IQR, and dispersion in integer milli; a distribution with fewer than four samples is `insufficient_samples`, not a value | Original Request; `src/analysis/market_institutions_policy.py:27-166`; `src/analysis/trade_networks_policy.py:55-120` | Task 5/7/10/11 |
| Market distributions and pairwise convergence/divergence use detached V4-20 `mktc-` memberships supplied as input rows; V4-21 mints or changes no market identity, and absent memberships are `missing` | Original Request "Measure convergence/divergence between markets"; `src/analysis/market_institutions_identity.py:38-98`; `src/analysis/market_institutions_detection.py:273-365` | Task 8/9/10/22 |
| Unit sources are closed to `owner_reference`, `observed_medium`, `exchange_counterpart`, `quoted`, and `unknown`; owner rows never override distributions and alignment is researcher-only | Original Request "reference units"; `src/analysis/market_institutions_expectations.py:50-395`; `src/experiments/migration_displacement_harvest.py:399-435` | Task 2/8/10/21 |
| Four metric families append 208 → **212**; the first 208 ids, order, versions, and value keys stay unchanged, and every suite and docs pin is swept in the same change | `src/analysis/specifications.py:53,75-285,8869-8917,9113-9141`; `src/analysis/metric_service.py:261-389,2549-2577` | Task 11/12/22/24 |
| Snapshot is a sibling `emergent-prices-snapshot-v1` with store `emergent-prices-store-v1`, two dual-gated settings, window-bound cursors, and seven GET-only routes failing closed with `emergent_prices_disabled`; it is not a runner/result/replay/SQL schema | `src/simulation/market_institutions_models.py`; `src/simulation/market_institutions_codec.py`; `src/simulation/market_institutions_ports.py`; `src/persistence/market_institutions_filesystem.py`; `src/infrastructure/settings.py:252-255,448-457,831-843`; `src/api/app.py:537-564,719-778` | Task 14/15/16/17 |
| No Godot overlay is added: price distributions are detached analytical structures; the presentation client is unchanged and its existing suite is the regression gate | Original Request; `.ai-factory/ARCHITECTURE.md` V3-40 through V3-42 seam; `clients/godot-observer/tests/run_protocol.gd` | Task 18/22/25 |
| Publication is programmatic and post-completion; no CLI producer and no runner flag is added | `src/experiments/market_institutions_publication.py:344-411`; V4-20 has no CLI producer | Task 16/25 |
| Off-gate experiment `emergent_prices@1` composes `markets_credit`, `subjective_valuation`, and `resource_exchange_profile` and never enters the V1 A–E gate | `src/experiments/catalog.py:2800-2835,5671-5706`; `src/experiments/market_institution_scenario.py:28-111` | Task 19/25 |
| Documentation covers `docs/emergent-prices.md`, README, ARCHITECTURE, DESCRIPTION, `docs/architecture.md`, `docs/configuration.md`, `docs/analysis-metrics.md`, `docs/research-api.md`, and the `docs/market-like-institutions.md` cross-link; roadmap registration stays with `$aif-roadmap` | ARCHITECTURE requirement 7; `.ai-factory/ROADMAP.md`; `docs/trade-networks.md` | Task 23/24/25 `git status` |

### Supported combinations and coverage transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| `markets_credit` off, valuation on | V3-18 only | No price mode, ledger, notice, metric input, or snapshot field; legacy bytes unchanged | Task 3/20 |
| `markets_credit` on, valuation off | V4-20 only | Price mode disabled; empty ledger; V4-20 experiment unchanged | Task 3/19 |
| `markets_credit` on, valuation on | Deterministic price mode and locked policy | `prcb-` ledger allocated; no write pair, schema, or v57 | Task 3/22 |
| Owner valuation with reference-kind reservation 1 | `owner_reference` unit | Expectation row carries valuation ratio and reservation | Task 2/8 |
| Acceptance memory kind with received ≥ 2 | `observed_medium` unit | Unit candidate and unit row; never names money | Task 2/8 |
| Exchange with one homogeneous kind per distinct side | `paired` evidence | One integer ratio sample per event | Task 6/7 |
| Homogeneous `ExchangeProposed`/`ExchangeWithdrawn` offer | `quoted` evidence | A separate quoted distribution; never pooled with completed samples | Task 6/7 |
| Exchange with a multi-kind side | `heterogeneous` | No ratio; excluded from distributions and counted | Task 6/7 |
| Exchange with the same kind on both sides | `same_kind` | No ratio; excluded | Task 6/7 |
| Ratio above 64,000 milli | `out_of_range` | No ratio; excluded | Task 6/7 |
| Same `(item_kind, unit, source_tick)` folded twice | Existing observation replaced | Counts, confidence, and ledger bytes unchanged | Task 2 |
| Fewer than four paired samples in a group | `insufficient_samples` | Distribution row with counts and no invented quantile | Task 7/11 |
| Four or more paired samples in one source | `available` | Quantiles, IQR, dispersion, sample count, five bin shares | Task 7/11 |
| Identical distributions in two markets | Distributions retained | `converged` relation with overlap ≥ 750 milli | Task 9/11 |
| Partly overlapping distributions | Distributions retained | `partially_converged` (250 ≤ overlap < 750) | Task 9/11 |
| Disjoint distributions | Distributions retained | `divergent` (< 250 milli) | Task 9/11 |
| No V4-20 memberships | Venue distributions only | Market rows empty, market coverage `missing`; no fabricated `mktc-` | Task 9/10 |
| No owner ledgers exported | Objective venue distributions | `expectation`/`quote` coverage `missing`; no fabricated owner rows | Task 8/13 |
| Owner row with no matching distribution | Owner row retained | Alignment `not_applicable`; distributions unchanged | Task 8 |
| `prc_v1` frame from an unrelated predicate | Ignored | No quote folded; no error | Task 4 |
| Malformed/oversize `prc_v1` frame | Dropped | One bounded warning count; simulation continues | Task 4/21 |
| Row or cap exceeded | Deterministic prefix | `coverage="partial"` plus one bounded truncation notice | Task 2/6/7/8/9/14/21 |
| Snapshot dual gate unset | No reader | 503 `emergent_prices_disabled` on all seven routes | Task 15/17 |
| Corrupt snapshot payload | No data | 500 `emergent_prices_store_corrupt` | Task 15/17 |
| Paged route with `window_index` | Filter-bound cursor | Only matching rows; cursor for another window rejected 400 | Task 14/17 |
| Publication disabled by the caller | No artifact | Nothing written; scientific status unchanged | Task 16 |
| Another unowned V4 flag | Unchanged | `capability_unimplemented`; fixtures repointed to `science` | Task 3/12/22 |
| Env-gated lane missing prerequisite | No green certification | `unexecuted` plus prerequisite | Task 25 |

No blocking open questions: every material decision is fixed below.

## Architecture and Decisions

1. **Deepen, do not claim.** V4-21 deepens the owned `markets_credit` context on
   the accepted `runner-config-v56` seam. It adds no V4 context, flag slot,
   `runner-config-v57`, root field, per-agent runner key, command, event,
   observer semantic type, write pair, `/v2` route, or migration. Counts remain
   14 contexts / 12 flags / 8 owned / 4 unowned.
2. **Build on V3-19, do not replace it.** The observed medium and acceptance
   evidence come from `resource_exchange_profile` and `AcceptanceMemoryLedger`.
   V4-21 interprets those as fallible owner unit candidates; it never labels a
   money good, currency, legal tender, store of value, or unit of account.
3. **Valuation is an input, not a price.** V3-18's owner-local `reservation`
   and `reference_kind` seed an expectation ratio. The engine and analysis never
   treat the reservation as an objective price or read it in exchange admission.
4. **One owner-scoped ledger.** `EmergentPriceLedger` stores bounded expectation
   rows keyed by `(item_kind, unit_kind, unit_source)` with observations, quotes,
   confidence, and notices. Ids are owner-local `prcb-`; no peer ledger, world
   state, item id, inventory, or record text is stored.
5. **Expectation math is fixed.** The weighted lower median combines valuation,
   observed exchange ratios, and sufficiently confident quotes. Confidence uses
   the exact integer formula in Task 2 and never becomes a score or ranking.
6. **Quoted offers are speech, not authority.** `prc_v1` frames carry act, item
   kind token, unit token, unit source, direction, ratio, confidence, and an
   optional anchor. They travel inside existing `Talk`/`Tell`; a received claim
   is evidence, never truth, and never raises an expectation above `expected`.
7. **No command-producing path.** The selected command is untouched except that
   one optional `prc_v1` relation may be attached to `Talk`/`Tell`. No `Move`,
   `Wait`, `Give`, or `NegotiateExchange` decision is changed by price beliefs.
8. **Evidence is paired or excluded.** A ratio exists only when each side of a
   committed exchange is homogeneous in one distinct kind. Multi-kind bundles,
   same-kind swaps, and out-of-range ratios are explicitly excluded and counted;
   they are never averaged into a canonical price.
9. **Distributions, not one price.** Every group reports sample count, min, p25,
   median, p75, max, IQR, dispersion, and five bin shares in integer milli, or an
   explicit `insufficient_samples` status. Completed and quoted sources are
   separate distributions and are never pooled. No single value represents a
   market.
10. **Market identity is borrowed, never minted.** Market distributions and
    cross-market relations consume detached `mktc-` membership rows supplied by
    the caller. V4-21 never creates, changes, splits, merges, or dissolves a
    V4-20 market. Absent memberships yield `missing` coverage.
11. **Convergence is distributional.** Pairwise convergence uses the overlap of
    quantile-bin shares (1000-scale) plus a median gap; thresholds are locked at
    750/250 milli. It is descriptive and never a score, ranking, or
    recommendation.
12. **Alignment is researcher-only.** Owner-versus-distribution and
    unit-versus-observed-medium alignment are `consistent`/`unresolved`/
    `inconsistent`/`not_applicable` and never reach cognition, prompts, memory,
    world state, observer semantics, or stop selectors.
13. **Bounded everything.** Evidence, owner rows, units, distributions, markets,
    relations, and snapshot families have independent policy caps with
    deterministic prefixes, `coverage="partial"`, and one bounded notice per
    family.
14. **Snapshot and read-only surfaces.** `emergent-prices-snapshot-v1` is a
    canonical sibling with digest and publication id and no wall-clock field;
    `emergent-prices-store-v1` is atomic, quota-bounded, idempotent, and
    corruption-safe; cursors bind `window_index`; seven GET-only dual-gated
    routes serve it. Publication is programmatic and post-completion.
15. **Clients and pins.** The Research UI adds one read-only panel; Godot gets no
    overlay. Four metrics append 208 → 212, every suite and docs pin is swept,
    and `emergent_prices@1` stays off the V1 gate. `$aif-roadmap` registers V4-21
    and re-confirms V4-17 through V4-20.

### Locked emergent-price summary

| Dimension | Locked behavior |
| --- | --- |
| Policy | `emergent-prices.v1` (cognition and analysis share the version token) |
| V4 ownership | `markets_credit` owned; 14 contexts / 12 flags / 8 owned / 4 unowned |
| Runner schema | `runner-config-v56` only; no v57, no new root/per-agent runner key |
| Activation | `markets_credit` **and** `subjective_valuation`; otherwise disabled |
| Valuation input | V3-18 `ValuationRow.item_kind`/`reference_kind`/`reservation` |
| Medium input | V3-19 `AcceptanceMemoryLedger` kind with `received_count ≥ 2` |
| Exchange primitives | Unchanged `NegotiateExchange`, `ExchangeProposed`, `ExchangeWithdrawn`, `ExchangeCompleted` |
| Cognition ledger | `prcb-` owner-local rows; 32 rows, 32 observations/row, 8 quotes/row, 8 units |
| Unit sources | `owner_reference`, `observed_medium`, `exchange_counterpart`, `quoted`, `unknown` |
| Expectation levels | `none`, `weak`, `expected`, `strong`; strong requires confidence ≥ 750 milli |
| Confidence | Integer 0-1000 from evidence count and ratio agreement (Task 2 formula) |
| Speech frame | `prc_v1`, 9 parts, 256 characters, one relation per `Talk`/`Tell` |
| Local behavior | Optional one-relation attachment only; no command replaced |
| Pairing classes | `paired`, `heterogeneous`, `same_kind`, `out_of_range` |
| Window | 32 ticks; index `tick // 32`; at most 512 windows |
| Distribution | sample source (`completed`/`quoted`), sample count, min/p25/median/p75/max, IQR, dispersion, and five bin shares in milli; min 4 samples per source |
| Market membership | Detached `mktc-` input rows; V4-21 mints no market identity |
| Convergence | Quantile-bin overlap plus median gap; overlap ≥ 750 and gap ≤ 250 `converged`, overlap < 250 or gap ≥ 750 `divergent`, else partial |
| Alignment | consistent ≤ 250 milli gap, inconsistent ≥ 750, else unresolved |
| Caps | Evidence 200k/200k; expectations 4,096; quotes 4,096; distributions 8,192; markets 1,024; relations 16,384; units 64 |
| Snapshot | `emergent-prices-snapshot-v1`; store `emergent-prices-store-v1`; 16 publications / 8 MiB; no wall-clock field |
| Routes | 7 GET-only under `SUBJECTIVE_DEBUG`; default limit 100; max 500; `emergent_prices_disabled` when unset |
| Catalog | 208 → 212 families; suite and docs pins swept to 212 |
| Clients | Research UI panel; no new Godot overlay |
| Experiment | `emergent_prices@1`, off the V1 gate |
| Pins | 43 commands; 73 observer semantics; replay-v27/codec `v25`; Alembic `0017`; `/v1`; `observer-protocol-v1` |

## Phase Index

1. [Phase 1: Contract and Owner-Scoped Price Cognition](phase-01-contract-and-owner-price-cognition.md) — Tasks 1-4
2. [Phase 2: Analysis Evidence and Detection](phase-02-analysis-evidence-and-detection.md) — Tasks 5-7
3. [Phase 3: Owner Joins, Market Distributions, Metrics, and Pins](phase-03-owner-joins-markets-metrics.md) — Tasks 8-12
4. [Phase 4: Collection and Publication](phase-04-collection-and-publication.md) — Tasks 13-16
5. [Phase 5: Read-Only Surfaces](phase-05-read-only-surfaces.md) — Tasks 17-18
6. [Phase 6: Experiment and End-to-End](phase-06-experiment-and-e2e.md) — Tasks 19-21
7. [Phase 7: Invariants and Pins](phase-07-invariants-and-pins.md) — Task 22
8. [Phase 8: Documentation and Verification](phase-08-docs-and-verification.md) — Tasks 23-25

## Cross-Phase Dependencies

- Task 2 depends on Task 1 (policy, enums, ids).
- Task 3 depends on Tasks 1-2 (ledger type and carry contract).
- Task 4 depends on Tasks 1-3 (frames, activation, ledger).
- Task 6 depends on Task 5 (policy, rows, window helpers).
- Task 7 depends on Task 6 (paired evidence rows).
- Task 8 depends on Tasks 5-7 (distributions to join).
- Task 9 depends on Tasks 6-7 and V4-20 membership inputs (market lift).
- Task 10 depends on Tasks 6-9 (evidence, detection, joins, relations).
- Task 11 depends on Task 10 (analysis object and locked keys).
- Task 12 depends on Task 11 (catalog count and ownership set).
- Task 13 depends on Tasks 3, 10, and 11 (result ledgers, analysis, metrics).
- Task 14 depends on Tasks 10 and 11 (row families and counts).
- Task 15 depends on Task 14 (snapshot codec).
- Task 16 depends on Tasks 13-15 (builder, snapshot, store).
- Task 17 depends on Tasks 14-16 (snapshot, store, publication).
- Task 18 depends on Task 17 (routes and schemas).
- Task 19 depends on Tasks 3-4, 11, and 13 (activation, metrics, collector).
- Task 20 depends on Tasks 16, 17, and 19 (publication, API, scenario).
- Task 21 depends on Task 20 (stable E2E fixtures).
- Task 22 depends on Tasks 1-21 (all pins).
- Task 23 depends on Task 22 (pins before prose).
- Task 24 depends on Task 23 (docs to pin).
- Task 25 depends on Tasks 20-22 and 24 (gates and docs).

## Tasks

### Phase 1: Contract and Owner-Scoped Price Cognition
- [x] Task 1: Lock `emergent-prices.v1` contract, policy, and identifiers ([details](phase-01-contract-and-owner-price-cognition.md#task-1-lock-emergent-pricesv1-contract-policy-and-identifiers))
- [x] Task 2: Add the owner-scoped emergent price ledger ([details](phase-01-contract-and-owner-price-cognition.md#task-2-add-the-owner-scoped-emergent-price-ledger)) (depends on 1)
- [x] Task 3: Activate and carry price expectations under `markets_credit` ([details](phase-01-contract-and-owner-price-cognition.md#task-3-activate-and-carry-price-expectations-under-markets_credit)) (depends on 1, 2)
- [x] Task 4: Add `prc_v1` speech frames with bounded quote attachment ([details](phase-01-contract-and-owner-price-cognition.md#task-4-add-prc_v1-speech-frames-with-bounded-quote-attachment)) (depends on 1-3)

### Phase 2: Analysis Evidence and Detection
- [x] Task 5: Lock the `emergent-prices.v1` analysis contract and caps ([details](phase-02-analysis-evidence-and-detection.md#task-5-lock-the-emergent-pricesv1-analysis-contract-and-caps))
- [x] Task 6: Extract bounded exchange-gathering evidence ([details](phase-02-analysis-evidence-and-detection.md#task-6-extract-bounded-exchange-gathering-evidence)) (depends on 5)
- [x] Task 7: Detect price distributions and cross-market relations ([details](phase-02-analysis-evidence-and-detection.md#task-7-detect-price-distributions-and-cross-market-relations)) (depends on 6)

### Phase 3: Owner Joins, Market Distributions, Metrics, and Pins
- [x] Task 8: Join detached expectations, quotes, and reference-unit alignment ([details](phase-03-owner-joins-markets-metrics.md#task-8-join-detached-expectations-quotes-and-reference-unit-alignment)) (depends on 5-7)
- [x] Task 9: Join market memberships and lift distributions to markets ([details](phase-03-owner-joins-markets-metrics.md#task-9-join-market-memberships-and-lift-distributions-to-markets)) (depends on 6-7)
- [x] Task 10: Compose the bounded `EmergentPricesAnalysis` harvest ([details](phase-03-owner-joins-markets-metrics.md#task-10-compose-the-bounded-emergentpricesanalysis-harvest)) (depends on 7-9)
- [x] Task 11: Append four price metric families (208 → 212) ([details](phase-03-owner-joins-markets-metrics.md#task-11-append-four-price-metric-families-to-212)) (depends on 10)
- [x] Task 12: Sweep suite-wide ownership and catalog pins ([details](phase-03-owner-joins-markets-metrics.md#task-12-sweep-suite-wide-ownership-and-catalog-pins)) (depends on 11)

### Phase 4: Collection and Publication
- [x] Task 13: Wire completed-run analysis and experiment collectors ([details](phase-04-collection-and-publication.md#task-13-wire-completed-run-analysis-and-experiment-collectors)) (depends on 3, 10, 11)
- [x] Task 14: Add `emergent-prices-snapshot-v1` models, codec, ports, and paging ([details](phase-04-collection-and-publication.md#task-14-add-emergent-prices-snapshot-v1-models-codec-ports-and-paging)) (depends on 10, 11)
- [x] Task 15: Add the atomic filesystem store and dual-gated settings ([details](phase-04-collection-and-publication.md#task-15-add-the-atomic-filesystem-store-and-dual-gated-settings)) (depends on 14)
- [x] Task 16: Compose and publish completed-run price snapshots ([details](phase-04-collection-and-publication.md#task-16-compose-and-publish-completed-run-price-snapshots)) (depends on 13-15)

### Phase 5: Read-Only Surfaces
- [x] Task 17: Add seven GET-only dual-gated price routes ([details](phase-05-read-only-surfaces.md#task-17-add-seven-get-only-dual-gated-price-routes)) (depends on 14-16)
- [x] Task 18: Add the Research UI price client and panel ([details](phase-05-read-only-surfaces.md#task-18-add-the-research-ui-price-client-and-panel)) (depends on 17)

### Phase 6: Experiment and End-to-End
- [x] Task 19: Register off-gate `emergent_prices@1` ([details](phase-06-experiment-and-e2e.md#task-19-register-off-gate-emergent_prices1)) (depends on 3-4, 11, 13)
- [x] Task 20: Add in-process price end-to-end coverage ([details](phase-06-experiment-and-e2e.md#task-20-add-in-process-price-end-to-end-coverage)) (depends on 16-17, 19)
- [x] Task 21: Add determinism, property bounds, and leakage coverage ([details](phase-06-experiment-and-e2e.md#task-21-add-determinism-property-bounds-and-leakage-coverage)) (depends on 20)

### Phase 7: Invariants and Pins
- [x] Task 22: Enforce architecture invariants and pin sweeps ([details](phase-07-invariants-and-pins.md#task-22-enforce-architecture-invariants-and-pin-sweeps)) (depends on 1-21)

### Phase 8: Documentation and Verification
- [x] Task 23: Documentation via `$aif-docs` ([details](phase-08-docs-and-verification.md#task-23-documentation-via-aif-docs)) (depends on 22)
- [x] Task 24: Add documentation pin and negative parity checks ([details](phase-08-docs-and-verification.md#task-24-add-documentation-pin-and-negative-parity-checks)) (depends on 23)
- [x] Task 25: Required-gate verification certification ([details](phase-08-docs-and-verification.md#task-25-required-gate-verification-certification)) (depends on 20-22, 24)

## Commit Plan

- **Commit 1** (after tasks 1-4): `feat(cognition): add owner-scoped emergent price expectations`
- **Commit 2** (after tasks 5-7): `feat(analysis): reconstruct exchange ratios and price distributions`
- **Commit 3** (after tasks 8-12): `feat(analysis): add market convergence, metrics, and catalog sweep`
- **Commit 4** (after tasks 13-18): `feat(simulation): publish emergent-price snapshots and read surfaces`
- **Commit 5** (after tasks 19-25): `test,docs: certify emergent-price experiment and required gates`

Commit checkpoints are suggestions only. Do not commit during `$aif-implement`
unless the user explicitly authorizes commits.

## Definition of Done

- V4-21 deepens `markets_credit`; 14 contexts / 12 flags / 8 owned / 4 unowned;
  no new context, flag slot, `runner-config-v57`, root field, or per-agent runner
  key; no money, currency, credit, banking, or debt behavior is implemented.
- Price cognition activates only when `markets_credit` and
  `subjective_valuation` are both present; every other combination leaves V3-18
  and V4-20 behavior unchanged.
- Exchange commands and events are unchanged; no field, admission rule, quantity,
  price, or unit is added to `NegotiateExchange`, `ExchangeProposed`,
  `ExchangeWithdrawn`, or `ExchangeCompleted`.
- The owner-scoped ledger stores item-kind tokens, unit kind/source, valuation
  reservation, observed ratios, quotes, expectation, confidence, counts, and
  notices; it stores no item ids, inventories, peer state, world state, money,
  credit, or debt.
- Repeated folding of the same `(item_kind, unit, source_tick)` leaves counts,
  confidence, and ledger bytes unchanged.
- `prc_v1` frames are bounded, strict, and carried only inside existing
  `Talk`/`Tell`; malformed or oversize frames are dropped with bounded warnings.
- No command is created or replaced; expectations never alter exchange
  admission, acceptance, counteroffers, or world state.
- Analysis reconstructs paired ratio evidence from committed events only and
  joins detached owner exports without reading `WorldState`, runtimes, stores, or
  API objects.
- Heterogeneous, same-kind, and out-of-range bundles are excluded and counted;
  no ratio is invented from a multi-kind side.
- Venue and market distributions report sample source, sample count, five
  quantiles, IQR, dispersion, and five bin shares in integer milli; completed and
  quoted sources stay separate; fewer than four samples is
  `insufficient_samples`.
- Market distributions join detached V4-20 `mktc-` memberships; V4-21 mints or
  changes no market identity, and absent memberships are `missing`.
- Convergence/divergence is pairwise, distribution-based, and descriptive;
  overlap ≥ 750 with median gap ≤ 250 is `converged`; overlap < 250 or gap
  ≥ 750 is `divergent`; otherwise partial, with `insufficient_evidence` below
  four samples per side.
- Expectation, quote, and unit coverage is `missing` when the detached input is
  absent; no edge or row is fabricated, and alignment never reaches cognition.
- Evidence, owner rows, units, distributions, markets, relations, and snapshot
  families are independently capped; truncation is deterministic and reported as
  `partial`, never complete.
- Four metric families append to exactly 212; prior ids/order/versions/value
  keys are unchanged; every suite pin is swept from 208 to 212 and no test
  expects `markets_credit` to be unowned.
- `emergent-prices-snapshot-v1` round-trips canonically with no wall-clock field;
  `emergent-prices-store-v1` is atomic, quota-bounded, idempotent, and
  corruption-safe; cursors bind the `window_index` filter.
- Seven GET-only dual-gated routes fail closed with `emergent_prices_disabled`,
  default limit 100, max 500, `window_index` ≤ 511; the Research UI panel is
  read-only; no new Godot overlay exists.
- Publication is programmatic and post-completion; no CLI producer or runner
  flag is added.
- Off-gate `emergent_prices@1` is registered and absent from the V1 gate.
- Commands stay 43; observer semantics stay 73; replay-v27/codec `v25` stay the
  maximum; Alembic stays `0017`; `/v1` and `observer-protocol-v1` stay.
- The in-process E2E uses real `WorldEngine` admission, real commands, real
  events, a real snapshot, and a real API read.
- Determinism across hash seeds, cap-bound properties, and leakage guards pass.
- Docs cover the page, README, ARCHITECTURE, DESCRIPTION,
  `docs/architecture.md`, `docs/configuration.md`, `docs/analysis-metrics.md`,
  `docs/research-api.md`, and the `docs/market-like-institutions.md` cross-link,
  with positive and negative parity checks; required
  gates are certified or explicitly `unexecuted`; the roadmap records V4-17
  through V4-21 and eight owned / four unowned.

## Verification Receipt

| Lane | Command | Result | Prerequisite / note |
| --- | --- | --- | --- |
| Unit + architecture correctness | `uv run pytest tests/unit tests/architecture -q` | 10,895 passed | Verification remediation rerun after the cross-source id/paging fix. |
| Focused price suites | `uv run pytest tests/unit/test_emergent_prices_*.py tests/architecture/test_emergent_prices_*.py -q` | 235 passed | Includes contract, ledger, analysis, metrics, catalog, snapshot, store, API, experiment, E2E, determinism, bounds, leakage, invariants, boundaries, paging concatenation, and docs parity. |
| Python coverage (focused) | `uv run pytest tests/unit/test_emergent_prices_*.py tests/architecture/test_emergent_prices_*.py -q --cov=src --cov-report=term` | 235 passed; whole-src 21% | Coverage enabled; the denominator is all of `src`. |
| Python coverage (full lane) | `uv run pytest tests/unit tests/architecture -q --cov=src --cov-report=term` | 10,894 passed; 79% whole-src (pre-remediation) | Remediation rerun measured 10,895 passed without coverage; focused post-remediation coverage is 21% whole-src. |
| Static: Ruff | `uv run ruff check src tests` | pass | No findings. |
| Static: mypy | `uv run mypy src tests` | pass | 2,536 source files, no issues. |
| Static: import boundaries | `uv run lint-imports` | pass | 25 contracts kept, 0 broken. |
| Integration (non-scale) | `uv run pytest tests/integration -m "not scale" -q` | 54 passed, 60 skipped, 5 deselected | DB-free lanes; skipped cases require external services. |
| Price store/API integration | `uv run pytest tests/integration/test_emergent_prices_store_api.py -q -m integration` | 1 passed | Real filesystem publish/read, idempotent republish. |
| Compose config | `docker compose config` | pass | Configuration renders. |
| Research UI tests | `cd clients/research-ui && ./node_modules/.bin/vitest run` | 300 passed (63 files) | Includes the emergent-price panel and disabled-state tests. |
| Research UI types | `cd clients/research-ui && ./node_modules/.bin/svelte-check --tsconfig ./tsconfig.app.json` | 0 errors, 0 warnings | Full app tsconfig. |
| Godot regression | `${GODOT_BIN}` existing suites | unexecuted | `GODOT_BIN` / `godot` is not installed in this environment; no Godot file changed. |
| Compose/browser acceptance | attested image + headed browser harness | unexecuted | No attested image or headed harness is available. |
| Benchmark regression (non-scale) | `uv run pytest tests/benchmarks -m "not scale" -q` | unexecuted | 20 deselected and 1 skipped; scale hardware and disposable PostgreSQL are absent. |

Verification remediation: cross-source quote, distribution, and relation ids now
include their source/sample discriminator; unit paging keys include
`unit_source`; paging concatenation is covered by a real completed+quoted
fixture; publication ids derive from the canonical payload digest;
`canonical_price_pair` was renamed to `canonical_exchange_pair`; stale current
208 pins and the V4 ownership line were corrected; the convergence wording now
matches the locked median-gap rule; and M8 registers V4-17 through V4-21.

The roadmap now records V4-17 through V4-21 in M8, re-confirms V4-17, V4-18,
V4-19, and V4-20, and states that eight V4 flags remain owned and four remain
unowned (`science`, `epidemics`, `ecological_feedback`, `disasters`).
