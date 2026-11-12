# Credit relationships

[← Research API](research-api.md) · [Back to README](../README.md) · [Market-like institutions](market-like-institutions.md)

## Overview

Credit relationships are one owner's beliefs about receive-now / repay-later
terms. V4-22 deepens the owned `markets_credit` context and extends the V3-17
promise/debt seam; it adds no bank, money, or enforceable obligation. A credit
row records what one owner believes about principal-like and repayment-like
item quantities, conditions, deadlines, and a collateral-like claim. Physical
principal and repayment remain ordinary `Give`/`ExchangeCompleted` commands.

## Non-goals

No bank, deposit, reserve, loan officer, interest rate, money, currency, legal
tender, enforceable debt, collection, credit score, ranking, allocation, quota,
global credit registry, or canonical credit exists. Credit rows are not shared
between owners and never grant permission.

## Activation

Credit cognition activates only when `markets_credit` is enabled and the V3-17
`structured_commitments` spec is present. V4-21 price expectations are optional:
when they are active, confidence contributes to willingness. Every other
combination leaves V3-17, V4-20, and V4-21 behavior unchanged.

## Owner ledger

One owner keeps a bounded `CreditRelationshipLedger` under policy
`credit-relationships.v1`. Rows carry a symmetric `crd-` anchor, an owner-local
`cred-` row id, direction (`owner_debtor`/`owner_creditor`), item-kind
principal/repayment quantities, a due tick, condition, collateral-like claim,
status, revisions, claims, trust, willingness, confidence, and notices.

Statuses are `proposed`, `accepted`, `open`, `partially_repaid`, `repaid`,
`defaulted`, `forgiven`, `disputed`, `withdrawn`, `declined`, and `expired`.
Caps are 32 rows, 16 claims per row, 8 revisions per row, and 8 counterparties.

Willingness is
`(trust*500 + history*300 + price_confidence*200) // 1000`, bounded to
`[0, 1000]`. Trust comes from the owner's directed relationship trust dimension.
The qualitative level (`none`, `weak`, `expected`, `strong`) is not a credit
score.

## crd_v1 frames

Credit acts travel as bounded `crd_v1` frames inside existing `Talk`/`Tell`
utterances. A frame has 16 colon-separated parts and at most 320 characters. At
most one credit relation is attached to an utterance. Malformed, oversize,
unknown, or unrelated frames are dropped with bounded warnings; a frame never
creates or replaces a command.

## Acts

The closed acts are `propose`, `accept`, `decline`, `repay`, `default`,
`renegotiate`, `forgive`, `dispute`, and `withdraw`. Every act is a declaration.
Repayment, default, renegotiation, forgiveness, and dispute change only the
owner's belief; they never move an item, collect a debt, impose a penalty, or
open a legal dispute.

## Analysis

Detached analysis reconstructs committed `crd_v1` claims and `Given` transfers
from events only. It emits descriptive performance outcomes, repayment-ratio
distributions (`proposed` and `agreed` samples are never pooled), counterparty
aggregates, and researcher-only owner alignment
(`consistent`/`unresolved`/`inconsistent`/`not_applicable`). Fewer than four
samples is `insufficient_samples`. Alignment never reaches cognition, prompts,
memory, world state, observer semantics, or stop selectors.

## Metrics

Four families append the catalog (212 -> 216):

- `credit_relationship_formation`
- `credit_repayment_performance`
- `credit_term_alignment`
- `credit_distribution_structure`

The first 212 families keep their ids, order, algorithm versions, and value
keys. Current catalog: 220 metric families.

## Snapshot, store, and routes

`credit-relationships-snapshot-v1` is a canonical sibling artifact with a
digest and publication id and no wall-clock field.
`credit-relationships-store-v1` stores publications atomically with quotas and
idempotent republish. Seven GET-only routes under
`/v1/simulations/{run_id}/credit-relationships` require `SUBJECTIVE_DEBUG`:

- summary
- `relationships`
- `claims`
- `performances`
- `distributions`
- `counterparties`
- `alignment`

Both `PALIMPSEST_CREDIT_RELATIONSHIPS_ROOT` and
`PALIMPSEST_CREDIT_RELATIONSHIPS_CURSOR_KEY` (at least 32 UTF-8 bytes) must be
set or every route fails closed with `credit_relationships_disabled`. Default
page limit is 100; maximum is 500; `window_index` is in `[0, 511]`.

## Experiment

`credit_relationships@1` is an off-gate experiment with four arms:
`cr-flag-off`, `cr-promises-only`, `cr-credit-on`, and `cr-credit-dialogue`.
It composes `markets_credit`, `structured_commitments`, and
`subjective_valuation` and never enters the V1 A-E gate.

## What this feature does not do

It adds no command, event, observer semantic type, runner schema, write pair,
SQL migration, `/v2` route, Godot overlay, money, bank, interest, enforceable
debt, credit score, or global credit registry.

## See also

- [Market-like institutions](market-like-institutions.md)
- [Emergent prices](emergent-prices.md)
- [Configuration](configuration.md)
- [Analysis metrics](analysis-metrics.md)
- [Research API](research-api.md)

## Accounting ledgers

Accounting interpretations of durable records are a separate owner-scoped seam;
see [Accounting ledgers](accounting-ledgers.md). Neither ledger is an objective
book of record.
