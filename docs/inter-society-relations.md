# Inter-society relations

[← Macro-societies](macro-societies.md) · [Back to README](../README.md) · [Analysis metrics →](analysis-metrics.md)

## What it is

Inter-society relations (ISR) are **researcher-only** analytics over ordered
pairs of analytical macro-society candidates (`msoc-`). Each pair is labeled
with a content-addressed `isr-` id. Panels cover eight closed evidence domains
and never feed cognition, memory, prompts, admission, stop selectors,
Observation, or Godot physics.

V4-15 deepens the analysis-only `macro_society_identity` context. It adds no
capability flag, no new context, no `runner-config-v57`, no command, event,
observer semantic type, write pair, `/v2` route, Godot overlay kind, or SQL
migration.

## What it is not

- Not a nation, alliance, treaty, war, border, or shared belief.
- Not an authoritative civilization relationship score, composite, bilateral
  score, alliance/enmity score, or trust score.
- Not agent knowledge: agents never receive pair analytics.
- Not a rewrite of diplomacy, organized-conflict, borders, or migration stores.

## Eight domain panels

| Domain | Detached evidence (counts / coverage only) |
| --- | --- |
| `cooperation` | Cross-membership cooperation / assistance |
| `hostility` | Conflict windows, diplomacy conflict lane, reciprocal harm |
| `exchange` | Completed exchanges / trade-lane evidence |
| `migration` | Journeys / movement between society residences |
| `trust_proxy` | Directed `TRUST` edges across different `msoc-` memberships |
| `agreement` | Diplomacy/treaty accept/promise and border agreement observations |
| `conflict` | `oc-` candidates joining both societies |
| `cultural_similarity` | `overlap_count` / `union_count` / `jaccard` / `*_mean_pairwise_similarity` + availability — never a field named `score` |

Each domain reports counts, coverage, and availability (`present` / `partial` /
`absent`) only.

## Time series and comparison

Fixed windows use `INTER_SOCIETY_RELATION_WINDOW_TICKS = 32`. Series are
append-only researcher views per ordered society pair.

Comparison is vectorial:

- two pairs via `pair_a` + `pair_b`, or
- one pair across windows via `pair_id` + `window_a` + `window_b`.

Mixed or incomplete operands fail closed. Comparison returns per-domain count
deltas and availability transitions only — never a single relationship rank.

## Metric families

Four families append after the V4-14 set, raising the catalog from 180 to
**184**:

- `inter_society_relation_structure@1`
- `inter_society_domain_evidence@1`
- `inter_society_relation_timeseries@1`
- `inter_society_pair_comparison@1`

They are additive beside the existing diplomacy family
`inter_society_relation_lanes@1` and must not rename or reuse it. The first 180
families keep id, order, version, and value keys. Emit gates on optional
`MetricComputationInputs.inter_society_relations_analysis`; empty inputs yield
empty value maps, never invented pairs.

## Publication and dual-gate API

Canonical artifact: `inter-society-relations-snapshot-v1` in
`inter-society-relations-store-v1`. Publication is opt-in, post-completion,
atomic, and quota-bounded; scientific status is isolated.

API attach requires **both**:

- `PALIMPSEST_INTER_SOCIETY_RELATIONS_ROOT`
- `PALIMPSEST_INTER_SOCIETY_RELATIONS_CURSOR_KEY` (≥32 UTF-8 bytes)

Otherwise routes return `503 inter_society_relations_disabled`.

CLI: `--inter-society-relations-root`, `--inter-society-relations-max-publications`
(default 16), `--inter-society-relations-max-bytes` (default 8_388_608).

## Read-only routes

Six GET routes under `/v1/simulations/{run_id}/inter-society-relations` require
`SUBJECTIVE_DEBUG`:

| Route | Result |
| --- | --- |
| `GET .../inter-society-relations` | summary |
| `GET .../inter-society-relations/pairs` | paged pairs |
| `GET .../inter-society-relations/pairs/{pair_id}` | pair detail |
| `GET .../inter-society-relations/pairs/{pair_id}/series` | pair time series |
| `GET .../inter-society-relations/comparison` | pair or window comparison |
| `GET .../inter-society-relations/windows` | paged windows |

Unknown published records return 404; corrupt store payloads return
`500 inter_society_relations_store_corrupt`; cursor mismatch is 400 and expiry
is 410.

## Research UI

View id `inter-society-relations` renders the eight domain panels, time series,
and comparison without composite-score chrome. Disabled publication maps to an
explicit unavailable state.

## Non-goals

- No new V4 flag or context; context map stays `v4-context-map-v2`.
- No Godot overlay kinds.
- No exclusive society partition; overlapping `msoc-` membership remains legal.
- No ROADMAP edit in this plan (`$aif-roadmap` owns milestone registration).

## See also

- [Macro-societies](macro-societies.md): `msoc-` endpoints reused by ISR pairs
- [Diplomacy](diplomacy.md): owner-scoped relations and lane metrics (distinct from ISR panels)
- [Analysis metrics](analysis-metrics.md): catalog families including the four ISR appendages

Current catalog: 220 metric families; 43 commands; 73 observer semantic types; Alembic `0017`.
