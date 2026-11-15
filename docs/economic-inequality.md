# Economic inequality

Economic inequality is a detached, longitudinal analysis surface. It measures
distributions and inequality indices over already-committed economic evidence:
physical possession, productive-tool access, infrastructure access, storage
access, declared credit relationships, and detached organizational-control
claims. It never asserts legitimate ownership, desert, merit, fault, poverty
status, or a welfare ranking, and it never feeds cognition, prompts, memory,
world state, observer semantics, or stop selectors.

## Overview

V4-24 adds the fifteenth V4 context, `economic_inequality`, as an analysis-only
context. It owns no world state, no owner state, and no capability flag. The
registry revision becomes `v4-context-map-v3`: 15 contexts, 12 flags, eight owned,
and four unowned.

The surface keeps three layers strictly separate:

| Layer | Content |
| --- | --- |
| Objective possession and access | Committed item custody, observed owner locations, operational infrastructure assets, store structures, and repositories. |
| Owner claim | Committed `crd_v1` credit declarations and detached organization-operation control rows. |
| Analytical comparison | Per-window distributions, indices, generation-cohort rows, and detached-society rows. |

No composite wealth, ownership, merit, poverty, legitimacy, or civilization
score exists. No dimension is pooled into another.

## Activation

Analysis activates only when committed events exist **and** at least one
economic channel is present:

- the V4 `organizations`, `markets_credit`, `infrastructure_networks`, or
  `supply_chains` capability flag; or
- the V3 `durable_records`, `structured_commitments`, or
  `subjective_valuation` spec.

When no channel is present, no analysis, no `economic_inequality_*` metric input,
and no snapshot field is produced; default V1/V2 bundles are unchanged.

## Dimensions and measures

Six dimensions are measured independently:

| Dimension | Measures |
| --- | --- |
| `resource_possession` | `observed_item_count` |
| `productive_tool_access` | `observed_tool_count` |
| `infrastructure_access` | `accessible_infrastructure_count` |
| `storage_access` | `accessible_storage_count` |
| `credit_relationship` | `claimed_principal_quantity`, `observed_repayment_quantity`, `claimed_relationship_count` |
| `organizational_resource_control` | `claimed_resource_control_count`, `claimed_storage_control_count` |

Possession comes from committed custody transitions. Access is physical presence
at the owner's last observed location plus operational infrastructure, store
structures, and repositories; it is never permission. Unknown recipe output or
structure kinds stay explicit and are excluded from tool/storage counts. An
owner without location evidence is excluded from access counts. Missing
dimensions are `unavailable`, never zero-filled.

Claims are testimony. Credit claims come from committed `crd_v1` relations and
never copy counterparty or item ids into snapshot-facing rows. Organizational
control comes from detached organization-operation harvest rows. Claims are
never netted against physical possession.

## Distributions and indices

Windows are 32 ticks with at most 512 windows. Each dimension row reports:

- owner and observed-owner counts;
- minimum, nearest-rank p25, median, p75, and maximum;
- IQR and dispersion (`maximum - minimum`);
- five equal-width bin shares in integer milli;
- quantized Gini, Theil T, Atkinson eps=1, and top-share in integer milli;
- a closed trend direction (`rising`, `falling`, `stable`,
  `insufficient_samples`, `unavailable`) using a 50-milli threshold.

Fewer than four observed owners yields `insufficient_samples` with counts
retained and no invented quantile, index, or share. Empty evidence is
`unavailable`. All-zero observed values are `available` with zero indices and
zero shares.

## Cohort and society comparisons

Cohorts are generation cohorts derived from committed `AgentCreated.generation_index`;
bootstrap owners are generation 0. A cohort row exists only with at least four
observed owners.

Society comparisons use detached `msoc-` analytical records over their recorded
window indexes. Overlap is legal and `overlap_member_count` counts owners in more
than one society once. Comparisons report distribution statistics over each
stratum's own Gini values and a closed longitudinal direction. They never rank,
label a best or worst, or produce a composite score.

## Legitimacy separation

Physical possession and ownership legitimacy are different layers. Objective
rows never carry claim or organization tokens or claim measures. Claim rows
never carry item ids, custody fields, or possession measures. Analytical rows
carry no owner ids, and snapshot rows carry no owner ids or raw owner tokens.
A hard leakage guard rejects mixed layers.

## Bounds

Independent caps apply to evidence events, owners, dimension rows, comparison
rows, cohorts, societies, notices, and snapshot bytes. Caps take deterministic
prefixes and set `coverage="partial"` with one bounded notice per family.

## Read-only surfaces

`economic-inequality-snapshot-v1` is canonical, digest-addressed, and
wall-clock-free. `economic-inequality-store-v1` is atomic, quota-bounded,
idempotent, and corruption-safe. Seven GET-only dual-gated routes serve it under
`SUBJECTIVE_DEBUG`:

- `GET /v1/simulations/{run_id}/economic-inequality`
- `/dimensions`
- `/possession`
- `/access`
- `/claims`
- `/cohorts`
- `/societies`

Pages default to 100 rows, cap at 500, and accept `window_index` up to 511.
Cursors bind the run, publication, digest, purpose, limit, and window; a cursor
from another window or dimension set is rejected. Reads are dual-gated by
`PALIMPSEST_ECONOMIC_INEQUALITY_ROOT` and
`PALIMPSEST_ECONOMIC_INEQUALITY_CURSOR_KEY` (at least 32 UTF-8 bytes); if either
is unset, every route returns 503 `economic_inequality_disabled`. A corrupt
store returns 500 `economic_inequality_store_corrupt`.

Publication is programmatic after successful completion; there is no CLI
producer, runner flag, or API write path. The Research UI adds one read-only
panel and Godot adds no overlay.

## Non-goals

There is no objective wealth, net worth, legitimate ownership, merit, poverty,
or welfare metric; no composite inequality score; no ranking; no partition of
owners; no money, price, credit score, or enforceable debt; no global
organization or society registry; no feedback into cognition, prompts, memory,
admission, or stop selectors; and no command, event, observer semantic type,
write pair, `/v2` route, handler migration, runner schema, or V4 capability
flag.

## Pins

The catalog is 244 metric families: six dimension families plus cohort and
society comparison families append positions 220-227 and keep the first 220
ids, order, versions, and value keys unchanged. Commands stay 43; observer
semantic types stay 73; the maximum replay/write pair is replay-v27 with codec
`v25`; Alembic head stays `0017`; the stable API is `/v1`; the observer protocol
stays `observer-protocol-v1`. V4 is currently 17 contexts on
`v4-context-map-v5`, 12 flags, eight owned, and four unowned. The off-gate experiment is `economic_inequality@1`.

## Verification

Focused unit, property, catalog, snapshot, store, route, Research UI, and
architecture tests cover the contract, evidence, detection, comparisons, metric
families, publication, dual gate, determinism, bounds, and leakage guards. The
in-process end-to-end path uses a real engine admission loop, real commands and
events, the completed-run builder, a finalized snapshot, the filesystem store,
and a read through the API. Env-gated Compose/browser acceptance and benchmark
lanes are recorded as `unexecuted` when their prerequisites are missing.

Intergenerational persistence over these economic outcomes is measured by [Social mobility](social-mobility.md); it adds no composite score.

See also: [Economic cascades](economic-cascades.md) measures how objective disruptions propagate through these production and infrastructure dependencies.
