# Emergent prices

V4-21 adds owner-scoped price expectations and analytical price distributions on
top of the already-owned `markets_credit` V4 context. It builds on V3-18
subjective valuation and V3-19 medium-of-exchange evidence. It does **not** add
a global price table, money, currency, credit, debt, allocation, quota, central
planner, ranking, severity, recommendation, new command, new event, new V4
context, new capability flag, runner schema bump, migration, or Godot overlay.

The human-readable feature name is "emergent prices"; identifiers and artifacts
use `emergent_prices` / `emergent-prices-*`.

## Non-goals

- No canonical price, price index, clearing price, price table, or market price.
- No money, currency, legal tender, numeraire, unit of account, store of value,
  credit, debt, bank, fee, tax, subsidy, quota, or allocation.
- No command-producing path: expectations never alter exchange admission,
  acceptance, counteroffers, or world state.
- No Godot presentation overlay and no observer protocol change.

## Activation

Price cognition is deterministic only when both conditions hold:

- `v4_capability_flags.markets_credit` is enabled; and
- the run declares the V3-18 `subjective_valuation` spec.

Every other combination is disabled and allocates no price ledger:

| `markets_credit` | `subjective_valuation` | Result |
| --- | --- | --- |
| off | on | V3-18 valuation only; no price ledger or notice |
| on | off | V4-20 market institutions only; no price ledger |
| on | on | deterministic `emergent-prices.v1` price mode |

The V3-19 `resource_exchange_profile` spec and `AcceptanceMemoryLedger` supply
observed-medium unit candidates. They remain descriptive and never name money or
a currency.

No runner root field, per-agent runner key, runner schema bump, or result
schema change is added. The runner result carries
`emergent_price_ledgers` as an owner-ordered tuple validated by the same
owner/cap discipline as other V4 ledgers.

## Owner ledger

`EmergentPriceLedger` is owner-local and bounded. A row is keyed by an item kind
and one unit candidate:

- `item_kind`: objective `ItemKind` token.
- `unit_kind`: another `ItemKind`, or `none`.
- `unit_source`: `owner_reference`, `observed_medium`,
  `exchange_counterpart`, `quoted`, or `unknown`.
- `expected_ratio_milli`, `confidence_milli` in integer milli.
- `level`: `none`, `weak`, `expected`, or `strong`.
- `valuation_reservation`, observation and quote counts, tick bounds.
- Bounded observations and quotes; ids are owner-local `prcb-` tokens.

Unit candidates come from the owner's reference-kind reservation, acceptance
memory rows with `received_count >= 2`, observed exchange counterparties, and
received `prc_v1` quotes. Candidate sources are deduplicated per unit and capped;
priority is `owner_reference`, `observed_medium`, `exchange_counterpart`,
`quoted`, `unknown`.

The expectation ratio is the deterministic weighted lower median of the
valuation ratio, observed exchange ratios, and quotes that meet the confidence
floor. Confidence uses the exact integer formula:

```
evidence = observations + contributing quotes
base     = min(600, evidence * 150)
spread   = (max_ratio - min_ratio) * 1000 // max(1, max_ratio)
agreement= 1000 - min(1000, spread)
confidence = min(1000, base + agreement * (1000 - base) // 2000)
```

`weak` requires fewer than two observations; `strong` requires at least two
observations and confidence at or above 750 milli; otherwise the level is
`expected`. A peer quote alone never raises a row above `none`.

Locked caps: 32 rows, 32 observations per row, 8 quotes per row, 8
counterparties, 8 units, 8 notices. Repeated folding of the same
`(item_kind, unit, source_tick)` is a no-op. Truncation is deterministic and
adds one bounded notice. Checkpoints carry exactly one owner's ledger; a
disabled mode clears it.

## `prc_v1` frames

Quoted offers and expectations travel only as one bounded relation inside an
already-selected `Talk` or `Tell`:

```
prc_v1:<predicate>:<item_kind>:<unit>:<unit_source>:<direction>:<ratio>:<confidence>:<anchor>
```

- Predicates: `prc_quote`, `prc_counter`, `prc_withdraw`, `prc_expect`.
- Acts: `quote_offer`, `quote_counter`, `withdraw_quote`, `cite_expectation`.
- Exactly nine colon-separated parts, at most 256 characters, no whitespace or
  control characters.
- One relation maximum per utterance; at most 32 existing relations are kept.
- Malformed, oversize, or unresolved frames are dropped with bounded warnings.

A received claim is evidence, never truth. It is stored as a `communicated`
quote and never becomes a canonical or authoritative price.

## Analysis

The detached analysis reads committed exchange events and token-only owner
export rows. It never reads `WorldState`, runtimes, stores, API objects, or peer
ledgers.

A ratio exists only when each side of an exchange is homogeneous in exactly one
distinct kind. The canonical pair orders kinds lexicographically. Pairing classes
are `paired`, `heterogeneous`, `same_kind`, and `out_of_range`; the last three
carry no ratio.

Every distribution reports:

- `sample_source`: `completed` or `quoted`; the two are never pooled.
- `sample_count`, minimum, p25, median, p75, maximum.
- `iqr_milli`, `dispersion_milli`, and five `bin_shares_milli` in integer milli.

Fewer than four paired samples yields `insufficient_samples`, not an invented
value. There is no single value that represents a market.

Owner expectations and quotes are joined one-way. Alignment is researcher-only:
`consistent` (gap ≤ 250 milli), `inconsistent` (gap ≥ 750), otherwise
`unresolved`, or `not_applicable` when no distribution exists. Owner rows never
create or change a distribution.

Market distributions consume detached V4-20 `mktc-` membership rows. V4-21 never
mints or changes a market identity. Absent memberships yield `missing` coverage
and no fabricated market.

Pairwise convergence uses the overlap of the five quantile-bin shares and a
median-gap guard: overlap ≥ 750 with median gap ≤ 250 is `converged`;
overlap < 250 or median gap ≥ 750 is `divergent`; otherwise
`partially_converged`; below four samples per side is `insufficient_evidence`.

Four layers stay separate: objective exchange evidence, owner expectation rows,
analytical distributions, and comparison relations. No layer contains a
canonical, global, or authoritative price field.

Analysis caps are locked at 200k exchange events, 200k quote events, 4,096
expectation rows, 4,096 owner quote rows, 8,192 distributions, 1,024 markets,
16,384 relations, 4,096 owners, 1,024 item kinds, and 64 units. Truncation is a
deterministic prefix with `coverage="partial"`.

## Metrics

Four families append to the catalog (208 → 212):

| Family | Value keys |
| --- | --- |
| `price_expectation_structure` | `window_tick`, `expectation_row_count`, `strong_count`, `expected_count`, `weak_count`, `valuation_row_count`, `mean_confidence_milli`, `expectation_coverage` |
| `price_distribution_dispersion` | `window_tick`, `distribution_count`, `completed_distribution_count`, `quoted_distribution_count`, `available_count`, `insufficient_count`, `mean_iqr_milli`, `mean_dispersion_milli`, `item_kind_count`, `unit_count`, `distribution_coverage` |
| `price_reference_unit_alignment` | `window_tick`, `unit_row_count`, `owner_reference_count`, `observed_medium_count`, `exchange_counterpart_count`, `quoted_count`, `consistent_count`, `unresolved_count`, `inconsistent_count`, `unit_coverage` |
| `market_price_convergence` | `window_tick`, `relation_count`, `converged_count`, `partially_converged_count`, `divergent_count`, `insufficient_count`, `mean_overlap_milli`, `market_pair_count`, `relation_coverage` |

All values are counts, tokens, or integer milli ratios. No family is a score,
ranking, severity, composite price, or recommendation.

## Snapshot, store, and routes

- Snapshot: `emergent-prices-snapshot-v1`
- Store: `emergent-prices-store-v1`
- Publication prefix: `prc-pub-`
- Snapshot caps: 64 units, 2,048 expectations, 2,048 quotes, 4,096
  distributions, 1,024 markets, 16,384 relations, 512 windows, 8 MiB artifact.
- The canonical document has no wall-clock field. Digests and publication ids
  are content-addressed; the publication id is `prc-pub-` plus the first 32 hex
  characters of the canonical payload digest.
- Completed and quoted rows, and multiple quotes within one window, have
  distinct ids so cursor paging never drops a row.
- The store is atomic, quota-bounded, idempotent for an identical digest, and
  corruption-safe.

Seven GET-only routes are dual-gated behind
`PALIMPSEST_EMERGENT_PRICES_ROOT` and `PALIMPSEST_EMERGENT_PRICES_CURSOR_KEY`:

- `/v1/simulations/{run_id}/emergent-prices`
- `/v1/simulations/{run_id}/emergent-prices/units`
- `/v1/simulations/{run_id}/emergent-prices/expectations`
- `/v1/simulations/{run_id}/emergent-prices/quotes`
- `/v1/simulations/{run_id}/emergent-prices/distributions`
- `/v1/simulations/{run_id}/emergent-prices/markets`
- `/v1/simulations/{run_id}/emergent-prices/relations`

Every route requires `subjective_debug`, defaults to 100 rows, caps at 500, and
accepts `window_index` up to 511. Cursors bind the window filter. Unset
settings fail closed with `emergent_prices_disabled`; missing publications are
404 `emergent_prices_run_not_found`; corrupt stores are 500
`emergent_prices_store_corrupt`; cursor problems are 400/410.

Publication is programmatic and post-completion. There is no CLI producer and no
runner flag.

## Experiment

`emergent_prices@1` is an off-gate experiment with four arms:

- `ep-flag-off`: no market flag, valuation, or exchange profile.
- `ep-valuation-only`: valuation and exchange profile, no market flag.
- `ep-prices-on`: market flag, valuation, and exchange profile.
- `ep-prices-quotes`: the same seams plus deterministic communication strategy,
  exercising the optional `prc_v1` relation on `Talk`/`Tell`.

The experiment is never added to the V1 A–E gate.

## What this feature does not do

- It does not create or replace a command.
- It does not change exchange admission, acceptance, counteroffers, or events.
- It does not label a money good, currency, unit of account, or store of value.
- It does not publish a canonical price or a market price index.
- It does not add a Godot overlay.
- It does not read another owner's ledger or live world state in analysis.

## See also

- [Market-like institutions](market-like-institutions.md)
- [Trade networks](trade-networks.md)
- [Analysis metrics](analysis-metrics.md)
- [Research API](research-api.md)
- [Configuration](configuration.md)
