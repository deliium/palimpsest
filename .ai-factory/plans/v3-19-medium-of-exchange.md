# Implementation Plan: V3-19 Emergent Medium of Exchange

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-12
Improved: 2026-10-12 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M7 — V3 Generational Civilization"
Rationale: Adds opt-in physical profiles, owner-scoped acceptance memory, and quantitative exchange-function indicators so research can watch whether durable transferable goods start to be traded onward, held, or used as a quote side, while `institutional_economy` stays unowned.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] mode=ultra treated as full (richer plan); remaining args describe the feature
INFO [aif-plan] resolved plan file: .ai-factory/plans/v3-19-medium-of-exchange.md (format=slug)
INFO [aif-plan] plan name prefix v3- applied per user request; suggested stem `v3-19-medium-of-exchange`; git.create_branches=false so stem is description slug (branch-derived naming disabled)
INFO [aif-plan] RESEARCH.md absent; research_influenced_plan=false
INFO [aif-plan] plan_default_milestone=auto would surface M6 first; scope is explicitly v3-19 under M7 so linkage uses M7
INFO [aif-plan] skill-context `.ai-factory/skill-context/aif-plan/SKILL.md` absent; no project override applied
INFO [aif-improve] refined 2026-10-12: select_checkpoint_schema agrees v16 before v15; codec supersets include v16; physical profile is a pure function; counteroffer spends inert items on the reference side only; quote kinds resolve from completed events; acceptance fingerprints dedupe; snapshot fields carry acceptance_memories

## Compatibility contract

This plan watches whether existing goods start to be used like a medium of exchange, a store of value, or a unit-like quote. It does **not** install money, and it does **not** own `institutional_economy`.

1. V1/V2 invariants intact. `WorldEngine` remains the only objective mutation authority. Agents receive immutable per-agent `Observation` / `Perspective` only. `WorldEvent` records remain immutable and append-only. Subjective numbers stay outside the objective fold. Godot remains read-only. Deterministic replay continues. No scripted `prices_converge` / `market_clears` / `institution_sets_price` / `money_emerges` outcomes.
2. Flag ownership unchanged: keep `cultural_historical_memory`, `generational_population`, and `kinship_inheritance` owned. Do **not** own `multi_polity_migration`, `institutional_economy`, or `multi_hop_testimony_tracking`. **No new V3 capability flag.** No currency, coin, shop, wage, tax, or market-clearing object.
3. Channel off = v3-18 baseline. With `resource_exchange_profile` absent, `NegotiateExchange` and `Give` behave as they do on `runner-config-v40`. `Talk` / `Ask` / `Tell` stay delivery-only. No acceptance ledger, no physical-profile object on the observation, no new metric rows. `exact_trajectory_hash` for existing experiments stays the same.
4. Schema bumps use accepted-set + exact key-set discipline. Never drop accepted V1/V2/V3 versions in the same change that adds a write version.
5. **No money object (locked).** Forbidden config and code aliases include the v3-18 set (`world_price`, `market_price`, `price_table`, `exchange_rate`, `currency`, `posted_price`, `clearing_price`, `numeraire`) plus `money`, `coin`, `currency_kind`, `legal_tender`, `is_money`, `medium_of_exchange`, `store_of_value`, `unit_of_account`. None of those strings may be a config key, a metric value key, an observation field, or an `ItemKind`. Display `Item.name` is never parsed.
6. **The engine still swaps named items, not roles (locked).** `NegotiateExchange` `accept` moves the item ids both commands listed. The engine does not read acceptance memory, physical-profile tokens, or valuation ledgers. A scripted accept of a poor deal still transfers.
7. **One physical vocabulary (locked).** Do not add an `ItemKind`. Do not add a stack quantity on `Item`. Do not add durability, spoil ticks, or a price field on `Item` or `WorldState`. `GENERIC` with `ItemLoad` 1 is the inert portable candidate. `FOOD` / `WATER` / `MATERIAL` / `TOOL` / `MEDICAL` stay what v3-18 already consumes or keeps.
8. **No single-threshold declaration (locked).** Metric documents expose counts and integer numerators/denominators. They do not contain a boolean, a `SupportBand`, or a label that names a kind as money. Do **not** add a `PhenomenonId`. Do **not** map the new families in `phenomenon_specifications._MAPPINGS`.
9. **Preserve v3-02–v3-18 locks:** reservations stay private; reference kind stays hunger/thirst (`FOOD` or `WATER`) and is still worth 1; concessions do not change the stored reservation; commitments stay unenforced; corpse custody is possession, not law; no global Culture / LibraryInstitution / `GlobalTechniqueRegistry`; a successful experiment is not knowledge; LLM drafts cannot name physics.

## Goal

The world already has transferable items with different physical fates: food can be eaten, materials can be crafted away, tools persist as instruments, and `GENERIC` is not eaten, drunk, fed, or consumed by craft. This plan makes those differences visible as a closed profile, lets an agent remember that a kind has been accepted in swaps they observed, and lets research count three patterns:

- the kind shows up often in completed trades
- the same item is acquired and later traded onward instead of consumed
- one side of an offer is homogeneous in that kind while the other side is something else

Nothing in the run writes "this kind is money".

## Design Decisions

### Invariant freeze (non-negotiable)

1. `WorldEngine` does not read acceptance memory, valuation ledgers, scarcity beliefs, or physical-profile tokens when it admits `NegotiateExchange`, `Give`, `Eat`, `Drink`, `Feed`, or craft.
2. Agents never receive another agent's acceptance memory or valuation ledger.
3. Research rows must not bias live cognition. `src/agents` does not import `src/analysis`.
4. No posted price, currency, or institution.
5. Godot remains read-only. No price tag and no money badge on the map.
6. Runs remain reproducible (explicit seeds, no acceptance RNG).
7. Free-text `Talk` is not parsed into a quote. Only `NegotiateExchange` history and the existing consume/transfer events feed the indicators.
8. A high count is a number in a research document. It does not flip a world flag and it does not change the next tick's physics.

### Scope split (locked)

| This plan (v3-19) | Deferred |
| --- | --- |
| Derived physical-profile tokens from existing `kind` + `load` | A new item kind, a coin, or a spoil clock |
| Owner-scoped acceptance memory from observed `ExchangeCompleted` | A shared numeraire or a world price |
| One extra reservation component, `observed_acceptance`, inside the existing `0..16` clamp | Changing the hunger/thirst reference kind |
| Proposer may spend an inert portable item on the reference side of a counteroffer when that component is at least 2 | An engine rule that prefers or requires that item, or a cognition path that opens the first offer |
| Three quantitative metric families | A `PhenomenonId`, a support band, or an `is_money` bit |
| `runner-config-v41` + codec `v16` only while the channel is on; replay stays 18 | Alembic `0018+`, `/v2` HTTP, protocol rename, owning `institutional_economy` |

**Rationale:** v3-18 lets two agents swap bundles and disagree about reservations. It does not remember that a pebble was accepted twice, and it does not count whether that pebble was eaten or passed on. Those observations are research questions. The only new cognition is a private tally so an agent can value a kind they have seen accepted, using the same reservation clamp. The tally is not a designation.

### Capability / ownership (locked)

1. **No new V3 flag.** Enabling the channel requires exact `resource_exchange_profile` on `runner-config-v41`, and that schema also requires the existing `subjective_valuation` object. Kinship, cultural memory, population lifecycle, commitments, reputation, and social norms are optional neighbors, not prerequisites.
2. **Do not** enable the channel implicitly when `subjective_valuation`, commitments, norms, or production are on.
3. **v40 without `resource_exchange_profile`** stays valid. Schema `v41` always requires both `subjective_valuation` and `resource_exchange_profile`.
4. Do **not** implement institutions, currency, kinship knowledge handoff, or cultural inheritance handoff.
5. Other unowned V3 flags still fail closed.
6. When the object is absent: behavior and hashes match the v3-18 channel for the same roster and seeds.
7. Optional read-only inputs, ignored by the engine:
   - Physical profile is `physical_profile(kind, load)` in `src/world/resource_profile.py`. `ObservedItem` already carries `kind` and `load`. The function is not stored on `Item`, `Observation`, or `WorldState`.
   - Acceptance counts come from `exchange_completed` occurrence facts in this owner's own observation, inside `acceptance_window_ticks`, deduped by fingerprint.
   - The reservation formula otherwise stays the v3-18 formula. Channel off, or no memory row, ⇒ `observed_acceptance` is omitted and contributes nothing. A missing row is not count `0`.

### Flag × object gate matrix (locked)

| Config shape | Allowed? | Reject / notes |
| --- | --- | --- |
| Object absent, schema v4–v40 | Yes (off) | Passthrough, including a present `subjective_valuation` on v40 |
| Object present, schema ≠ v41 | No | `resource_exchange_profile_requires_v41` |
| Schema v41 without the object | No | `v41_requires_resource_exchange_profile` |
| Schema v41 without `subjective_valuation` | No | `resource_exchange_profile_requires_subjective_valuation` |
| Object present, any V3 flag off | Yes | No flag is required |
| Any forbidden money or price alias | No | `resource_exchange_profile_money_forbidden` |
| `mode=disabled` present | No | `resource_exchange_profile_mode_invalid` — omit the object for off |
| Unowned V3 flag true | No | existing `capability_unimplemented` |

### Runner schema (locked)

Introduce `RUNNER_SCHEMA_VERSION_V41 = "runner-config-v41"`:

- Exact root key set = **v40 accepted roots** (the object `subjective_valuation` stays required) ∪ sibling **`resource_exchange_profile`**.
- `resource_exchange_profile` present ⇒ `schema_version == runner-config-v41`.
- Decode v23–v40 synthesizes `resource_exchange_profile=None`.
- Gate rewrite: cultural, durable, historical-layer, repository, genealogy, experimentation, possession, structured-commitment, and subjective-valuation allowlists that were extended to v40 in v3-18 also accept v41. Do not require the new object for those channels.
- Default write stays `runner-config-v4` when all V3 flags are off and both objects are absent.
- **Write pair:** when the channel is active, `checkpoint_schema_for_production` returns `(EVENT_SCHEMA_REPLAY_V18, "v16")`, higher priority than `subjective_valuation_active` `(18, "v15")`. Channel off does not select `v16`. Replay stays 18 because this plan adds no event type. Add keyword `resource_exchange_profile_active: bool = False`.
- **Agreement chain:** `select_checkpoint_schema` in `src/simulation/engine.py` currently agrees `subjective_valuation_active` only with codec `v15`. A v41 run has both flags on, so the profile clause must be first: profile active agrees `(18, "v16")`; valuation without the profile still agrees `(18, "v15")`. Pass the keyword through all three `select_checkpoint_schema` call sites in `engine.py`, plus the call sites in `runner.py` and `service.py`. Mirror `_bind_subjective_valuation_channel` with an engine flag set from the config object.
- **Loop kwargs:** `_resource_exchange_profile_loop_kwargs` in `src/simulation/runner.py`, beside `_subjective_valuation_loop_kwargs`, passes `resource_exchange_profile_active` and `acceptance_window_ticks` into `CognitiveLoop`. The world rule context does **not** carry the window. The engine never sees the ledger.
- **Matrix finalize (Task 10 only):** in `src/experiments/matrix_schema.py`, insert `resource_exchange_profile_on` immediately before `subjective_valuation_on`. Task 1 must **not** edit finalize priority.
- Alembic head stays `0017`. Protocol id stays `observer-protocol-v1`. Command count stays **38**. Semantic tuple stays **61**.

### Serialization contract (locked)

Mirror the v40 helper pattern in `runner_serialization.py`:

- v41 root keys = v40 family helper ∪ `{resource_exchange_profile}` minus optional objects that are absent, except `subjective_valuation` which v41 requires
- Exact child keyset `_RESOURCE_EXCHANGE_PROFILE_KEYS`
- `_encode_resource_exchange_profile` / `_decode_resource_exchange_profile` with `_require_keys`
- Encode: `schema_version == V41` requires both objects
- Decode: v23–v40 → `None`
- DEBUG log `present`, `policy_id`, `acceptance_window_ticks` on decode
- Reject forbidden money and price aliases before key acceptance

### `ResourceExchangeProfileSpec` (locked)

Root sibling object; omit for off. Exact keys (reject extras / missing):

| Key | Type / values | Role |
| --- | --- | --- |
| `policy_id` | `resource-exchange-profile-v1` only | Closed policy id |
| `acceptance_window_ticks` | int, `1..256` | How recent an observed completion may be and still update memory. Not a price decay |

No designated kind, no weight table, no threshold at which a kind "becomes" money.

### Runtime channel flags (locked)

1. `resource_exchange_profile_active = config.resource_exchange_profile is not None` at run start. This implies `subjective_valuation_active` because v41 requires that object.
2. Pass no new rule context into `evaluate_operation`. `NegotiateExchange` keeps the v3-18 `SubjectiveValuationRuleContext` only.
3. Subjective checkpoint field `acceptance_memories` (owner id → ledger). Blank-slate key of the same name. Not a SQLAlchemy table. The same name is a field on `SubjectiveSnapshot`, `CognitiveLoopProposal`, and `CognitiveLoopResult` in `src/agents/cognition/models.py`, and on the matching contract in `src/agents/cognition/contracts.py`, using the same require-owner helper pattern as `subjective_valuations`.

### Physical profile (locked)

Module `src/world/resource_profile.py`. Pure function `physical_profile(kind, load)` of `ItemKind` and `ItemLoad`. Not stored on `Item`, `ObservedItem`, `Observation`, or `WorldState`. Do not edit `perception.py`. Cognition calls the function when the channel is on. Channel off never calls it, so the observation stays the v3-18 shape.

Closed tokens, all derived:

| Token | When |
| --- | --- |
| `perishable_body` | `FOOD` or `WATER` |
| `craft_consumed` | `MATERIAL` |
| `instrument` | `TOOL` |
| `restorative` | `MEDICAL` |
| `inert` | `GENERIC` |
| `portable` | `load` value `<= 1` |
| `bulky` | `load` value `>= 2` |

Every kind gets exactly one of `perishable_body`, `craft_consumed`, `instrument`, `restorative`, `inert`, plus exactly one of `portable` or `bulky`, in that token order. The caller passes `kind` and `load` from the item it already sees. It does not read `Item.name`.

DEBUG log `physical_profile_derived kind=… tokens=…` when the function runs.

### Acceptance memory (locked)

Module `src/agents/cognition/acceptance_memory.py`. Owner-scoped.

A row is `item_kind`, `received_count` (`0..64`), `giver_ids` (tuple of at most 8 distinct body id strings), `tick`. The ledger also stores the last 32 applied fingerprints, each `(source_tick, actor_id, counterparty_id, give item ids, take item ids)`.

Fold inside `_prepare_subjective_valuations` from occurrence facts whose `kind` is `exchange_completed`. `ExchangeCompleted.actor_id` is the acceptor: `give_*` arrives at the counterparty, and `take_*` arrives at the actor. Perception already puts both kind tuples on those facts.

- Skip the occurrence when `observation.tick - provenance.source_tick > acceptance_window_ticks`.
- Skip the occurrence when its fingerprint is already in the last 32. A second completion in the same tick has a different fingerprint and still applies. Re-folding the same occurrence does not.
- For every kept occurrence, increment both arriving sides. Each kind on `give_item_kinds` gains `+1` with giver `actor_id`. Each kind on `take_item_kinds` gains `+1` with giver `counterparty_id` (`other_entity_id` on the occurrence). Clamp `received_count` at 64. Append a giver id if absent, dropping the oldest id past 8.
- `Give`, `Talk`, and proposals do not update memory. A proposal is not an acceptance.
- Leaving the location does not erase rows. A newborn has no rows. A missing row is not count `0`. Do not copy another owner's rows.

DEBUG log `acceptance_memory_updated owner_id=… item_kind=… received_count=… giver_count=… tick=…`.

### Valuation component (locked)

Extend `appraise_reservation` in `src/agents/cognition/subjective_value.py`. Signature gains `observed_acceptance: int | None = None`. `None` (channel off or no row) omits the component. An int is the closed map:

| `received_count` | Contribution |
| --- | --- |
| row missing (`None`) | omitted |
| `1..2` | `+1` |
| `3..7` | `+2` |
| `>= 8` | `+3` |

Token string `observed_acceptance`. It joins the existing parts before the `0..16` clamp. Reference kind is unchanged and still stores reservation `1` with no components. The component may raise a non-reference kind (including `GENERIC`) so a private bundle test can accept it. It does not create a shared unit.

DEBUG log stays `valuation_appraised`, now including the new token when present.

### Proposer preference (locked)

`propose_exchange_command` only answers a proposal already on the observation. It does not open an offer. Scripted arms still submit the first offer. The preference lives in `_counter_or_withdraw`, and only on the reference-priced give side (`own_reference` today). When the give side is the tool, leave the tool ids as they are.

Channel on, while filling that reference side:

- Target value is the tool reservation (today's `count`, because each reference item is worth 1).
- Walk held items in `entity_id` order. An item is eligible when `physical_profile` contains both `inert` and `portable` and the `observed_acceptance` component is `>= 2`.
- Append eligible ids while the summed reservations stay within `max_bundle` and the running give value is still below the target. Each eligible item contributes its own reservation, not 1.
- Then append reference-kind ids at value 1 until the give value reaches the target or `max_bundle` is full.
- `filled` means both sides are non-empty and the give value is at least the target. A shortfall withdraws, matching today's failure path. Do not emit `accept` from this branch.
- Channel off keeps `own_reference[:count]` and the existing `len(give) == count` check.

DEBUG log `exchange_give_preference owner_id=… item_id=… item_kind=… acceptance_component=…`.

### Research indicators (locked)

New module `src/analysis/exchange_functions.py`. Not imported by `WorldEngine`. `layer` is `research_inference`. Empty harvest when `resource_exchange_profile` is absent.

Forbidden keys on every row: `price`, `rate`, `money`, `currency`, `numeraire`, `is_money`, `medium_of_exchange`, `store_of_value`, `unit_of_account`, `support_band`, `threshold`.

Per `ItemKind`, three documents. Values are ints or null when the denominator is 0. No floats.

**`exchange_acceptance_share`**

From `ExchangeCompleted` only:

| Field | Meaning |
| --- | --- |
| `completed_swap_count` | Completed exchanges in the trace |
| `kind_present_count` | Swaps where the kind appears on either side |
| `kind_received_count` | Swaps where the kind is on the side that arrives |
| `giver_breadth` | Distinct body ids who gave the kind away |
| `share_num` | `kind_present_count` |
| `share_den` | `completed_swap_count` |

**`exchange_acquisition_fate`**

Per item id, first matching later event wins. An item enters the table only when an event names it: `give` where `resulting_holder_id` is the recipient, `exchange_completed` on an arriving side, `resource_harvested` with `created_item_id`, or a craft output event that already carries a created item id. Tick-0 placement with no such event is not an acquisition. Consume events: `eat`, `feed`, `drink` with `consumed_item is True`, `craft_started.consumed_item_ids`. Transfer events: a later `give` or `exchange_completed` where that id leaves the holder. On `exchange_completed`, `give_item_ids` leave `actor_id` and `take_item_ids` leave `counterparty_id`.

| Field | Meaning |
| --- | --- |
| `acquired_count` | Item ids of this kind acquired |
| `later_transferred_count` | Those later transferred with no earlier consume |
| `consumed_count` | Those later consumed with no earlier transfer |
| `still_held_count` | Acquired and neither consumed nor transferred by the trace end |
| `median_hold_ticks` | Integer median of ticks from acquisition to the fate event. Even counts use the lower of the two central values. Null when no fate event |

**`exchange_quote_homogeneity`**

Read `subjective_valuation_events` (the full event tuple already passed by `src/experiments/collectors.py`). `ExchangeCompleted` carries `give_item_kinds` and `take_item_kinds`. `ExchangeProposed` carries ids only. Build an id→kind map from completed-exchange pairs, then from `Fed.item_kind`. An id missing from that map stays unresolved. A proposal with any unresolved id counts as a non-quote. Do not add kinds onto `ExchangeProposed`.

A homogeneous quote for kind K: one side is non-empty and every resolved item on it is K, and the other side contains at least one item whose kind is not K. If both sides qualify, count K and the other kind once each. `quote_den` is the same on every row: the count of `ExchangeProposed` plus `ExchangeCompleted` in the trace. `paired_item_count_median` uses the lower central value when the count is even.

| Field | Meaning |
| --- | --- |
| `homogeneous_side_count` | Quotes where this kind is the homogeneous side |
| `nonquote_count` | Events in the trace that are not a homogeneous quote for any kind |
| `paired_item_count_median` | Integer median of how many items sat on the other side. A bundle size, not a price |
| `reference_row_count` | Detached valuation rows whose `reference_kind` equals this kind |
| `quote_num` | `homogeneous_side_count` |
| `quote_den` | Count of `ExchangeProposed` plus `ExchangeCompleted` |

`paired_item_count_median` must not be named `price` or `rate` in code, docs, or UI.

DEBUG log `exchange_functions_assembled family=… kind=… num=… den=…` per emitted row.

### Metric catalog (locked)

`METRIC_FAMILY_COUNT` **80 → 83**. Append, in order:

- `EXCHANGE_ACCEPTANCE_SHARE` / `exchange_acceptance_share@1`
- `EXCHANGE_ACQUISITION_FATE` / `exchange_acquisition_fate@1`
- `EXCHANGE_QUOTE_HOMOGENEITY` / `exchange_quote_homogeneity@1`

`assemble_metric_documents` calls the assembler only when `MetricComputationInputs.resource_exchange_profile_spec` is not null. The assembler reads the existing `subjective_valuation_events` and `subjective_valuation_ledgers` fields. Do not add a second event channel. `src/experiments/collectors.py` sets `resource_exchange_profile_spec` from the arm config when the object is present, beside the existing subjective-valuation replace. `censoring_policy` text: counts describe observed transfers; they do not name a money good.

Research UI (`clients/research-ui/src/epistemic.ts`, `AnalyticsPanel.svelte`): add the three ids to `ANALYTICAL_OVERLAYS` and a `RESOURCE_EXCHANGE_PROFILE_FAMILIES` list. Badge copy: "acceptance share", "acquisition fate", "quote homogeneity". Epistemic class stays `research_inference`. Do not use the words price or money in the badge.

Godot: no new label and no new overlay.

### Experiment AV (locked)

Id `exchange_functions@1`. Builder `experiment_av_exchange_functions` in `src/experiments/catalog.py`. Export from `src/experiments/__init__.py`. Add to `OFF_GATE_MATRIX_EXPERIMENT_IDS`. Off the V1 gate. Four arms:

| condition id | What it shows |
| --- | --- |
| `av-channel-off` | Object absent. Metrics empty. A v40 swap still completes. `ObservedItem` has no profile attribute, because this plan never adds one. |
| `av-inert-unused` | Channel on. A `GENERIC` item with load 1 sits unused and is never named by an acquisition event. `later_transferred_count == 0` and `consumed_count == 0`. Do not require `acquired_count > 0`. No forbidden key appears. |
| `av-later-trade` | Scripted completions: the generic item moves A→B against food, then B→C against a tool, and is never eaten. `later_transferred_count >= 1`, `consumed_count == 0`, `kind_present_count >= 2`. Output has no boolean emergence flag. |
| `av-quote-kind` | Two `ExchangeCompleted` events: one homogeneous `GENERIC` side against a `TOOL`, and one homogeneous `FOOD` side against a `TOOL`. Both kinds have `homogeneous_side_count >= 1`. Kinds come from the completed event, not from a proposal id lookup. The document does not pick a winner. |

Scripted arms submit the offer before the accept in the same tick, matching v3-18. A unit test seeds acceptance memory and asserts `_counter_or_withdraw` spends an inert portable id on the reference give side before food. That test is not a claim that money emerged.

## Commit Plan

- **Commit 1** (after tasks 1–3): `feat: describe transferable goods without naming a currency`
- **Commit 2** (after tasks 4–7): `feat: let agents remember which goods were accepted in trade`
- **Commit 3** (after tasks 8–10): `feat: count exchange patterns without declaring money`
- **Commit 4** (after task 11): `docs: describe exchange-function indicators`

## Tasks

### Phase 1: Channel and physical profile

- [x] Task 1: Add `RUNNER_SCHEMA_VERSION_V41`, `ResourceExchangeProfileSpec`, exact encode/decode, and the flag×object reject codes.

  Deliver `runner-config-v41` in `src/simulation/runner_models.py` and the v41 helpers in `src/simulation/runner_serialization.py`. Exact child keys are `policy_id` (`resource-exchange-profile-v1`) and `acceptance_window_ticks` (`1..256`). v41 requires `subjective_valuation` and `resource_exchange_profile`. v23–v40 decode the new object as `None`. v40 with only `subjective_valuation` stays valid. Reject forbidden money and price aliases with `resource_exchange_profile_money_forbidden` before key acceptance. Extend the v40 allowlists through v41 without requiring the new object. Do not edit `matrix_schema.py` in this task. Do not add a V3 flag.

  LOGGING REQUIREMENTS:
  - DEBUG on decode: `present`, `policy_id`, `acceptance_window_ticks`
  - INFO when a config is rejected, including the stable reason code
  - ERROR with the schema version when encode is missing a required object
  - Logger name `simulation.runner_serialization`
  - Levels follow the process log config; no code edit is required to quiet production

  Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `tests/unit/test_runner_config_v41.py`

- [x] Task 2: Add codec `v16` as a superset of codec `v15`, and select `(EVENT_SCHEMA_REPLAY_V18, "v16")` only when the channel is active. (depends on 1)

  `checkpoint_schema_for_production` gains `resource_exchange_profile_active: bool = False` and returns `(18, "v16")` ahead of subjective valuation's `(18, "v15")`. Codec `v16` carries every v15 payload, including `exchange_offers`, `subjective_valuations`, and `scarcity_beliefs`, plus `acceptance_memories`. Codecs through `v15` omit that key and reject it if present. In `src/simulation/serialization.py`, every valuation or commitment check written as `codec == "v15"` or `codec in {..., "v15"}` also accepts `"v16"`. `acceptance_memories` stays v16-only. In `src/simulation/engine.py`, every restore membership test whose newest codec is `"v15"` also includes `"v16"`. `select_checkpoint_schema` agrees profile active with `(18, "v16")` before the existing valuation `(18, "v15")` clause. Pass `resource_exchange_profile_active` into all three `select_checkpoint_schema` call sites in `engine.py` and into the call sites in `runner.py` and `service.py`. Bind the flag on the engine the same way `_bind_subjective_valuation_channel` binds valuation. Replay fold stays on schema 18. No new event. Pass `acceptance_window_ticks` only through `_resource_exchange_profile_loop_kwargs` into `CognitiveLoop`. Do not put the window on the world rule context.

  LOGGING REQUIREMENTS:
  - INFO `checkpoint_schema_selected` with `schema_version`, `codec`, and `reason=resource_exchange_profile_active`
  - DEBUG when `acceptance_memories` is encoded or omitted, with owner count
  - WARN if a pre-v16 payload contains `acceptance_memories`
  - WARN if `select_checkpoint_schema` is asked for the profile and the agreed pair is not `(18, "v16")`
  - Logger names `simulation.persistence`, `simulation.serialization`, and `simulation.engine`

  Files: `src/simulation/persistence.py`, `src/simulation/serialization.py`, `src/simulation/runner.py`, `src/simulation/service.py`, `src/simulation/engine.py`, `tests/unit/test_codec_v16.py`

- [x] Task 3: Add `physical_profile(kind, load)` as a pure function. (depends on 1)

  Add `src/world/resource_profile.py` with the closed token table in the design. Return the token tuple in the locked order. Do not add a field to `ObservedItem`, `Observation`, `Item`, or `WorldState`. Do not edit `src/simulation/perception.py` or `src/world/_perception.py`. Callers pass the `kind` and `load` they already have. Do not read `Item.name`. Channel-off observations stay the v3-18 shape because nothing new is attached.

  LOGGING REQUIREMENTS:
  - DEBUG `physical_profile_derived` with `kind` and the token list
  - No INFO on the per-call path
  - Logger name `world.resource_profile`

  Files: `src/world/resource_profile.py`, `tests/unit/test_resource_profile.py`

### Phase 2: Private acceptance and the proposer

- [x] Task 4: Add the owner-scoped acceptance-memory ledger, blank-slate deny key, and v16 checkpoint restore. (depends on 2)

  Implement `src/agents/cognition/acceptance_memory.py` with the row shape, fingerprint list, and clamps in the design. Blank-slate deny-list in `src/simulation/new_agent_initialization.py` gains `acceptance_memories`. Add the field to `SubjectiveSnapshot`, `CognitiveLoopProposal`, and `CognitiveLoopResult` in `src/agents/cognition/models.py`, and to the matching contract in `src/agents/cognition/contracts.py`, with a require-owner helper beside `require_owner_subjective_valuations`. Restore and commit the ledger in `src/simulation/agent_runtime.py` the same way as `subjective_valuations`. Export the empty-ledger and require-owner helpers from `src/agents/cognition/__init__.py` if valuations are exported there. A newborn ledger is empty. Do not treat a missing kind as received-count `0`.

  LOGGING REQUIREMENTS:
  - DEBUG `acceptance_memory_updated` with owner, kind, `received_count`, `giver_count`, tick
  - DEBUG `acceptance_memories_carried` with owner id and row count, matching the valuation carry log
  - INFO when a blank-slate entrant starts with an empty ledger
  - Logger names `agents.cognition.acceptance_memory` and `simulation.agent_runtime`

  Files: `src/agents/cognition/acceptance_memory.py`, `src/agents/cognition/models.py`, `src/agents/cognition/contracts.py`, `src/agents/cognition/__init__.py`, `src/simulation/new_agent_initialization.py`, `src/simulation/agent_runtime.py`, `src/simulation/serialization.py`, `tests/unit/test_acceptance_memory.py`

- [x] Task 5: Add the `observed_acceptance` reservation component without changing the reference kind. (depends on 4)

  Extend `appraise_reservation` with `observed_acceptance: int | None = None` and the `+1/+2/+3` map. `None` omits the token. The sum stays clamped to `0..16`. When `item_kind` is the reference kind, the row is still reservation `1` and components stay empty. Existing v3-18 callers that omit the argument keep today's numbers, including Alice 8 and Bob 3.

  LOGGING REQUIREMENTS:
  - DEBUG `valuation_appraised` includes the `observed_acceptance` token and amount when it contributed
  - DEBUG `valuation_acceptance_omitted` when the argument is `None`
  - ERROR if a caller passes a bool or an int outside `0..64`
  - Logger name `agents.cognition.subjective_value`

  Files: `src/agents/cognition/subjective_value.py`, `tests/unit/test_subjective_value.py`

- [x] Task 6: Update acceptance memory from this owner's observed completions and pass the window into the loop. (depends on 4, 5)

  On each cognitive pass, while the channel is on, fold `exchange_completed` occurrence facts inside `_prepare_subjective_valuations`. Use `provenance.source_tick` for the window. Skip a fingerprint already in the last 32, and still apply a second completion in the same tick when the fingerprint differs. Increment both arriving sides: `give_item_kinds` with giver `actor_id`, `take_item_kinds` with giver `counterparty_id`. Ignore proposals, withdrawals, `Give`, and `Talk`. Do not import analysis. Do not write the ledger onto `WorldState`. `CognitiveLoop` and `build_cognitive_loop` gain `resource_exchange_profile_active: bool = False` and `acceptance_window_ticks: int = 32`. The runner splat comes from Task 2's kwargs helper.

  LOGGING REQUIREMENTS:
  - DEBUG per folded event: owner, source tick, kinds incremented, fingerprint accepted or skipped
  - DEBUG when an event is outside the window (`acceptance_event_ignored`)
  - DEBUG when a fingerprint repeats (`acceptance_fingerprint_skipped`)
  - INFO at loop start with `resource_exchange_profile_active` and the window
  - Logger name `agents.cognition.loop`

  Files: `src/agents/cognition/loop.py`, `src/agents/cognition/configuration.py`, `src/simulation/runner.py`, `tests/unit/test_acceptance_memory_loop.py`

- [x] Task 7: Let a counteroffer spend a remembered inert portable item on the reference give side before food. (depends on 3, 5, 6)

  Change only `_counter_or_withdraw` in `src/agents/cognition/subjective_value.py`. `propose_exchange_command` still only answers an existing proposal. When the give side is the tool, keep the tool ids. When the give side is the reference bundle and the channel is on, fill it as the design locks: eligible `inert` + `portable` items with `observed_acceptance >= 2`, entity-id order, each at its own reservation, then reference items at 1, until the give value reaches the tool reservation or `max_bundle` is full. `filled` means both sides are non-empty and the give value meets the target. A shortfall withdraws. Channel off keeps `own_reference[:count]` and `len(give) == count`. Do not edit `WorldEngine` or `_rules.py`.

  LOGGING REQUIREMENTS:
  - DEBUG `exchange_give_preference` with owner, item id, kind, and component
  - DEBUG `exchange_give_preference_skipped` with the reason (`channel_off`, `below_component`, `not_inert`, `tool_side`, `bundle_rejected`)
  - No log line may contain a price or a money label
  - Logger name `agents.cognition.subjective_value`

  Files: `src/agents/cognition/subjective_value.py`, `tests/unit/test_exchange_give_preference.py`

### Phase 3: Quantitative indicators

- [x] Task 8: Classify acceptance share, acquisition fate, and quote homogeneity without a money label.

  Add `src/analysis/exchange_functions.py` implementing the three views in the design. Inputs are `subjective_valuation_events` plus detached valuation rows. `ExchangeCompleted` supplies kinds. `ExchangeProposed` kinds come from the id→kind map built from completed pairs and `Fed.item_kind`. An unresolved proposal id makes that proposal a non-quote. `quote_den` is the count of both event types, identical on every row. Acquisition ignores tick-0 items that no event names. Integer medians use the lower central value when the count is even. Consume kinds are `eat`, `feed`, `drink` when `consumed_item` is true, and `craft_started.consumed_item_ids`. Do not add an event. Reject forbidden keys if a caller tries to set them. Return an empty result when the spec is absent. `WorldEngine` must not import this module.

  LOGGING REQUIREMENTS:
  - DEBUG `exchange_functions_assembled` per family and kind with numerator and denominator
  - DEBUG `exchange_functions_skipped` when the spec is absent
  - WARN if a row would have contained a forbidden key; refuse the row
  - Logger name `analysis.exchange_functions`

  Files: `src/analysis/exchange_functions.py`, `tests/unit/test_exchange_functions.py`

- [x] Task 9: Register the three metric families and the research-UI badges. (depends on 8)

  Bump `METRIC_FAMILY_COUNT` from 80 to 83. Append the three `MetricFamilyId` members and `_spec_*` builders in the order listed under Metric catalog. Add `resource_exchange_profile_spec` to `MetricComputationInputs`. `assemble_metric_documents` calls the assembler only when that spec is present, and passes the existing `subjective_valuation_events` and `subjective_valuation_ledgers`. Set the spec in `src/experiments/collectors.py` next to the subjective-valuation `replace`. Stamp `layer=research_inference`. Do not add a `PhenomenonId` and do not edit `_MAPPINGS`. Research UI badges use the three plain phrases in the design and stay analytical. Godot files stay untouched.

  LOGGING REQUIREMENTS:
  - INFO when the assembler returns zero documents because the channel is off
  - DEBUG with family id and row count when documents are emitted
  - ERROR if `validate_metric_catalog` count drifts from 83
  - Logger name `analysis.metric_service`

  Files: `src/analysis/specifications.py`, `src/analysis/metric_service.py`, `src/analysis/exchange_functions_metrics.py`, `src/experiments/collectors.py`, `clients/research-ui/src/epistemic.ts`, `clients/research-ui/src/views/AnalyticsPanel.svelte`, `tests/unit/test_exchange_function_metrics.py`

- [x] Task 10: Register off-gate Experiment AV and the matrix factor. (depends on 6, 7, 9)

  Add `experiment_av_exchange_functions` (`exchange_functions@1`) with the four arms in the design. Put the id on `OFF_GATE_MATRIX_EXPERIMENT_IDS`. This task is the only one that edits `src/experiments/matrix_schema.py`: insert `resource_exchange_profile_on` immediately before `subjective_valuation_on`. Assert the later-trade and quote arms contain the quantitative fields and contain none of the forbidden keys. The unused arm asserts `later_transferred_count == 0` and `consumed_count == 0` and does not require `acquired_count > 0`. The quote arm uses two `ExchangeCompleted` events so both kinds are on the event. Assert `av-channel-off` does not change a v40 swap hash and does not add a field to `ObservedItem`.

  LOGGING REQUIREMENTS:
  - INFO at scenario build with condition id and whether the profile object is present
  - DEBUG with the indicator counts the arm asserts
  - No log line declares a kind to be money
  - Logger name `experiments.catalog`

  Files: `src/experiments/catalog.py`, `src/experiments/__init__.py`, `src/experiments/matrix_schema.py`, `tests/unit/test_experiment_av.py`

### Phase 4: Docs

- [x] Task 11: Document the channel, the three indicators, and the still-unowned economy flag. (depends on 1–10)

  Update `docs/analysis-metrics.md` with a section for the three families (off the V1 gate, count 83). Update the architecture note that already says analysis must not feed cognition: state that acceptance share, acquisition fate, and quote homogeneity are counts, and that no threshold names a currency. Record `runner-config-v41`, codec `v16` with replay still 18, command count still 38, semantic tuple still 61, and `institutional_economy` still unowned. Route the wording through the docs checkpoint `/aif-implement` already requires when Docs is yes.

  LOGGING REQUIREMENTS:
  - No runtime log. The checkpoint text must not introduce a money alias as a supported config key.
  - If a doc command fails, ERROR the path and the exit status in the implementation log.

  Files: `docs/analysis-metrics.md`, `docs/architecture.md`

<!-- Commit checkpoint: tasks 1-3, 4-7, 8-10, 11 -->
