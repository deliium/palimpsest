# Social mobility

## Overview

V4-25 adds the sixteenth V4 context, `social_mobility`, as detached analysis over
already-owned V3 genealogy and V4 economic/institutional evidence. It measures
intergenerational persistence across six independent outcome domains and never
assigns a social class, caste, stratum, elite, or underclass label. There is no
composite mobility score, merit verdict, prestige score, inheritance right, or
feedback into cognition, prompts, memory, admission, or stop selectors.

The analysis is read-only and opt-in. Activation requires committed events, at
least one committed `KinshipEdgeRecorded`, and an outcome channel. Without
kinship evidence no analysis, metric input, or snapshot field is produced, so
default V1/V2 runs are unchanged.

## Activation

- Committed objective events must be present.
- At least one committed `KinshipEdgeRecorded` parent→child edge must exist.
- At least one outcome channel must be present: a V4 economic/institutional
  configuration seam, or detached practical-knowledge, teaching, or
  organization-operation evidence.

Founder identity comes from `runner_config.agents` (`agent_id` ↔ body id).
Mid-run identity comes from committed `AgentCreated`, `AgentEnteredWorld`, and
`AgentInitializationRecorded` rows. One immutable identity map translates every
agent-id-keyed audit into the same body-token space used by objective events.
Unmapped owners are reported and dropped, never guessed.

## Domains and evidence

Each domain has exactly one measure. Missing evidence is `unavailable`; it is
never zero-filled and never imputed from another domain.

| Domain | Measure | Evidence source | Layer |
| --- | --- | --- | --- |
| `resources` | `observed_resource_item_count` | committed possession rows minus observed tools | objective outcome |
| `skills` | `known_technique_count` | distinct active `PracticalKnowledgeAudit` `content_key` values | owner outcome |
| `social_influence` | `inbound_communication_partner_count` | distinct committed `Talked`/`Asked`/`Told` senders | objective outcome |
| `organization_roles` | `held_organization_role_count` | distinct believed `office_id` assignments, excluding rejected stances | owner outcome |
| `educational_access` | `educational_access_receipt_count` | `TeachingAudit` rows plus `RepositoryMemberRetrieved` events | objective outcome |
| `productive_assets` | `observed_productive_asset_count` | observed tools plus operational infrastructure plus accessible storage | objective outcome |

`productive_assets` is an additive count of observed physical assets. It is not
wealth, net worth, or a composite score.

The eight metric families are `resource_mobility@1`, `skill_mobility@1`,
`social_influence_mobility@1`, `organization_role_mobility@1`,
`educational_access_mobility@1`, `productive_asset_mobility@1`,
`social_mobility_generation_lag@1`, and `social_mobility_coverage@1`.

## Ancestor and descendant pairing

Genealogy comes only from committed `KinshipEdgeRecorded` edges and
`AgentCreated.generation_index`. Bootstrap owners are generation 0. Ancestor
chains are depth-bounded (`max_lineage_depth=8`). An ancestor quantity is the
latest observation at or before a window boundary; a descendant quantity uses
the same boundary. Ancestor observation never uses a post-birth value.

Each pair reports its generation lag and both observation windows. Unresolved
pairs are retained with no invented quantity or bin.

## Mobility and persistence statistics

- Windows are 32 ticks (`window_index = tick // 32`, at most 512 windows).
- Quantile rank bins default to 5.
- Reported statistics are same-bin persistence share, upward share, downward
  share, mean absolute rank change, and quantized Spearman rank correlation in
  integer milli.
- Fewer than 8 resolved pairs in a window/domain is `insufficient_samples`;
  counts are retained and no bins, shares, or correlation are invented.
- Persistence labels are closed to `persistent` (same-bin share ≥ 500 milli),
  `mobile`, `insufficient_samples`, and `unavailable`.

Bins are statistical positions, never named strata.

## Generation lags and many-generation studies

Generation indices are capped at 32. Lag strata 1–4 are computed independently;
each lag recomputes its own bins and shares from its own pair sample. Lags are
never pooled into one score, and no generation is labeled best or worst.

## Coverage and bounds

Each family has an independent cap with a deterministic prefix: 200k events,
4,096 owners, 4,096 pairs, 4,096 domain rows, 1,024 generation rows, 2,048 lag
rows, 1,024 coverage rows, and 8 notices. Exceeding a cap sets
`coverage="partial"` and adds one bounded notice. Corrupt, truncated, and
unmapped inputs are explicit; a partial analysis never becomes a zero.

## Read-only surfaces

`social-mobility-snapshot-v1` is canonical, digest-addressed, and wall-clock
free. `social-mobility-store-v1` stores it atomically with quotas, idempotent
republish, and corruption detection. Publication is programmatic after
completion; there is no CLI producer or runner flag.

Seven GET-only routes require `SUBJECTIVE_DEBUG` and are dual-gated by
`PALIMPSEST_SOCIAL_MOBILITY_ROOT` plus
`PALIMPSEST_SOCIAL_MOBILITY_CURSOR_KEY` (≥32 UTF-8 bytes). When either setting
is absent every route fails closed with `social_mobility_disabled`.

- `GET /v1/simulations/{run_id}/social-mobility`
- `GET /v1/simulations/{run_id}/social-mobility/domains`
- `GET /v1/simulations/{run_id}/social-mobility/economy`
- `GET /v1/simulations/{run_id}/social-mobility/human-capital`
- `GET /v1/simulations/{run_id}/social-mobility/standing`
- `GET /v1/simulations/{run_id}/social-mobility/generations`
- `GET /v1/simulations/{run_id}/social-mobility/coverage`

Default limit is 100, maximum 500, and `window_index` is bounded to 0–511.
Cursors bind the run, publication, digest, purpose, limit, window filter, and
last key; a mismatched cursor is rejected. The Research UI panel is read-only
and no Godot overlay is added.

## Non-goals

- No social class, caste, stratum, elite, or underclass label.
- No objective mobility verdict, merit, desert, or prestige score.
- No composite cross-domain mobility index.
- No inheritance right or legitimate-heir adjudication.
- No legitimate-ownership, welfare, or poverty adjudication.
- No feedback into cognition, prompts, memory, admission, or stop selectors.
- No global social registry or world actor.

## Pins

17 V4 contexts / 12 V4 flags / eight owned / four unowned; map
`v4-context-map-v6`; 244 metric families; 45 commands; 73 observer semantic
types; replay-v27 / codec `v25`; Alembic `0017`; `/v1`;
`observer-protocol-v1`.

`.ai-factory/ROADMAP.md` is stale for V4-23, V4-24, and V4-25 and is owned by
`$aif-roadmap`; this plan does not edit it.

## Verification

Focused unit/architecture suites cover contract closure, identity translation,
genealogy caps, six-domain outcomes, quantized statistics, generation lags,
analysis bounds, eight metric families, snapshot/codec/paging/ports, the atomic
store, publication receipts, seven routes, the Research UI panel, determinism,
and leakage guards. See the V4-25 plan bundle for the verification receipt.

Current catalog: 275 metric families; 45 commands; 73 observer semantic types; Alembic `0017`.

See also: [Economic cascades](economic-cascades.md) measures how objective disruptions propagate through these production and infrastructure dependencies.
