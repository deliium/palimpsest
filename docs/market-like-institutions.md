# Market-like institutions (V4-20)

## Overview

V4-20 owns the declared `markets_credit` V4 context and implements **market-like
institutions only**. It does not implement credit, banking, debt, money, or
prices, and there is no global `Market` class or authoritative price.

The feature is one bounded, owner-scoped belief channel over repeated exchange
gatherings. Repeated own-observed exchange at a location can form a meeting
expectation, social schedules, emergent role claims, and opaque record anchors;
detached analysis then describes venue recurrence and market-like persistence
from committed events. Nothing is scheduled or scripted into existence.

`$aif-roadmap` owns roadmap registration. V4-17, V4-18, V4-19, and V4-20 are
currently unregistered in M8, and the owned V4 flag count must be recorded as
eight.

## Mechanics

Each agent may keep a bounded `market-institutions.v1` ledger of its own observed
exchange venues. The ledger stores only:

- venue observations keyed by `(venue_id, source_tick)` with own-observed
  exchange, proposal, and withdrawal counts;
- a meeting expectation (`none`, `weak`, `expected`, `strong`);
- optional social schedules (`single_occurrence`, `recurring_interval`,
  `periodic_window`, `unknown`);
- broker-like role claims (`broker`, `host`, `organizer`, `unknown`) whose
  recognition requires an office or organization basis;
- opaque exchange-record anchors;
- closed notices.

It never stores inventories, item ids, item kinds, prices, valuations, peer
ledgers, or world state. Owner-local ids are `mktb-`; analysis ids are `mkt-ven-`
and `mktc-`.

Exchange remains `NegotiateExchange` and `ExchangeCompleted` with unchanged
fields and admission. V4-20 adds no trade initiation, demand, price, or
allocation mechanism. Analysis attributes a completion to
`occurrence.origin_location_id`; exchange offers remain V3-18 behavior.

## Emergence loop

The supported loop is:

1. an owner observes repeated exchange at one logical location;
2. observations accumulate into `weak`, `expected`, or `strong` expectations;
3. schedules, role claims, and record anchors can be adopted from own evidence
   or bounded `mkt_v1` speech;
4. an otherwise idle owner may attend an expected adjacent venue;
5. detached analysis reports recurrence, persistence, and forward-only lineage.

No step is guaranteed. A peer frame or a single observation never mints a venue
or a strong expectation.

## Expectations and schedules

One observation yields `weak`; two yield `expected`; two observations plus a
schedule of confidence at least 500 milli yield `strong`. A claim or peer frame
alone never mints a venue or a strong expectation.

Schedules are owner-scoped social beliefs, active only by an integer tick rule.
`recurring_interval` uses `(tick - phase_tick) % interval_ticks == 0`;
`periodic_window` uses `tick // 32 == window_index`. They are not world timers,
calendars, or events, and no V3 convention situation is widened.

Meeting expectations, schedules, role claims, and record anchors travel as
bounded `mkt_v1` relations inside existing `Talk`/`Ask`/`Tell`; no speech command
is added. An otherwise idle owner may replace `Wait` with one `Move` to an
observed adjacent exit whose destination is an expected or persistent venue.
There is no pathfinding, multi-hop travel, lookahead, or global catalog.

## Roles and brokers

A broker exists only as an owner belief with role kind `broker` and basis
`office` or `organization`; only those bases can set `recognized=true`. Host,
organizer, and unknown role claims follow the same recognition rule. There is no
broker actor, fee, commission, discount, or enforcement field. Analysis reports
broker-like participation as counts, never as an appointment.

## Exchange records

Exchange records are opaque references to existing durable records or
repositories. The ledger never dereferences or asserts their truth, and analysis
never reconstructs record text. A record anchor is a bounded token, not a market
record, receipt, or title.

## Derivation

`analysis.market_institutions_*` reads committed events only and produces:

- gatherings: at least two completions and two parties in one 32-tick window;
- venues: `single_gathering`, `recurring_gathering`, `market_like_persistent`, or
  `dormant`, with integer recurrence milli and at most one dormant row per venue;
- market candidates: contemporaneous venue components connected by shared
  participants, with `mktc-` content-addressed identity;
- forward-only lineage across every consecutive window, including empty windows
  (`emerged`, `continued`, `transformed`, `split`, `merge`, `dissolved`);
- detached owner expectation, role, and record rows with researcher-only
  alignment (`consistent`, `unresolved`, `inconsistent`, `not_applicable`).

The analysis never reads `WorldState`, an agent runtime, a store, or an API
object. Alignment is descriptive for researchers only and never reaches
cognition, prompts, memory, world state, stop selectors, or observer semantics.

## Bounds and coverage

A venue requires at least two exchanges and two distinct parties in a window.
Persistence requires at least three active windows and at least 500 milli
recurrence. Expectations, roles, records, venues, gatherings, participation,
markets, and lineage are independently capped; truncation is deterministic and
never reported as complete.

An absent owner lane reports `missing`, a truncated or unresolved lane reports
`partial`, and no row is fabricated. A venue emits at most one dormant follow-up
row, never an unbounded tail.

## Read-only surfaces

`market-institutions-snapshot-v1` is a canonical sibling artifact with a digest
and publication id and no wall-clock field. `market-institutions-store-v1`
stores it atomically with bounded publication and byte limits. Neither is a
runner config, result schema, replay schema, or SQL schema.

Seven GET-only routes serve the published artifact under `SUBJECTIVE_DEBUG`:

- `/v1/simulations/{run_id}/market-institutions`
- `/v1/simulations/{run_id}/market-institutions/venues`
- `/v1/simulations/{run_id}/market-institutions/gatherings`
- `/v1/simulations/{run_id}/market-institutions/expectations`
- `/v1/simulations/{run_id}/market-institutions/roles`
- `/v1/simulations/{run_id}/market-institutions/records`
- `/v1/simulations/{run_id}/market-institutions/markets`

Default page size is 100, the maximum is 500, and `window_index` is bounded to
0-511. Cursors bind the `window_index` filter; a cursor for another window is
rejected. Missing gates return `market_institutions_disabled`; a corrupt store
returns `market_institutions_store_corrupt`.

The Research UI adds one read-only panel. The Godot observer is unchanged and
adds no overlay.

## Configuration

Both `PALIMPSEST_MARKET_INSTITUTIONS_ROOT` and
`PALIMPSEST_MARKET_INSTITUTIONS_CURSOR_KEY` (at least 32 UTF-8 bytes) are
required for the read routes. Either setting missing yields
`market_institutions_disabled`.

Publication is programmatic and post-completion; there is no CLI producer and no
runner flag. Callers opt in by constructing a publisher after scientific
completion. The receipt's `stored` value never changes scientific status.

## Metrics

The catalog appends `market_venue_recurrence@1`, `market_venue_persistence@1`,
`market_expectation_structure@1`, and `market_role_structure@1`, raising the count
from 204 to **208**. The first 204 families keep their ids, order, versions, and
value keys. The families report counts, availability, closed tokens, and integer
milli ratios only.

## Read-only fields

The API exposes published analysis rows only: venue and gathering counts, closed
venue/expectation/role/record status tokens, recurrence and alignment milli
values, market and lineage identifiers, coverage, and truncation flags. The
Research UI renders those values without computing a score or rank.

## Non-goals

- No price, price index, money object, currency, numeraire, bid, ask, spread,
  fee, commission, tax, debt, credit limit, allocation, quota, or central
  planner exists.
- No market score, ranking, severity, recommendation, or suggested action
  exists.
- No new command, event, observer semantic type, write pair, runner schema,
  `/v2` route, or migration is added; no later runner-config schema exists.
- No authoritative record, title, receipt, or truth claim exists.
- No Godot market overlay exists.
- No central exchange, clearing house, bank, or enforced credit exists.

## Verification

Local lanes:

- `uv run pytest tests/unit/test_market_institutions_*.py tests/unit/test_supply_chain_pins.py tests/architecture/test_market_institutions_*.py -q`
- `uv run pytest tests/integration/test_market_institutions_store_api.py -q -m integration`
- `uv run ruff check src tests`
- `uv run mypy src tests`
- `uv run lint-imports`

Pins: 14 contexts / 12 flags / eight owned / four unowned; 208 metric families;
43 commands; 73 observer semantic types; replay-v27 / codec `v25` maximum when
selected; Alembic `0017`; `/v1`; `observer-protocol-v1`; off-gate
`market_institutions@1`. Roadmap registration remains with `$aif-roadmap`.

## See also

- [Architecture](architecture.md)
- [Configuration](configuration.md)
- [Analysis metrics](analysis-metrics.md)
- [Research API](research-api.md)
- [Trade networks](trade-networks.md)
