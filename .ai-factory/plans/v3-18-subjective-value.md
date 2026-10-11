# Implementation Plan: V3-18 Subjective Valuation and Barter

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-11
Improved: 2026-10-11 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M7 — V3 Generational Civilization"
Rationale: Adds owner-scoped valuations and structured barter so agents can disagree about what a tool is worth and still complete a physical swap when both name the same bundles.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] mode=ultra treated as full (richer plan); remaining args describe the feature
INFO [aif-plan] resolved plan file: .ai-factory/plans/v3-18-subjective-value.md (format=slug)
INFO [aif-plan] plan name prefix v3- applied per user request; suggested stem `v3-18-subjective-value`; git.create_branches=false so stem is description slug (branch-derived naming disabled)
INFO [aif-plan] RESEARCH.md absent; research_influenced_plan=false
INFO [aif-plan] plan_default_milestone=auto would surface M6 first; scope is explicitly v3-18 under M7 so linkage uses M7
INFO [aif-improve] refined 2026-10-11: codec v15 is a v14 superset; exchange_offers on WorldState (no prices); channel-on colocated holdings; scarcity counts others' visible items; inventory ignores the one held unit; Alice 8 / Bob 3 without the world model; engine restore and snapshot ledger fields; metric rows store reservations and kind counts

## Compatibility contract

This plan adds private valuations and a bilateral item swap. It does **not** own `institutional_economy`, and it does **not** install a price the world can read.

1. V1/V2 invariants intact. `WorldEngine` remains the only objective mutation authority. Agents receive immutable per-agent `Observation` / `Perspective` only. `WorldEvent` records remain immutable and append-only. Subjective numbers stay outside the objective fold. Godot remains read-only. Deterministic replay continues. No scripted `prices_converge` / `market_clears` / `institution_sets_price` outcomes.
2. Flag ownership unchanged: keep `cultural_historical_memory`, `generational_population`, and `kinship_inheritance` owned. Do **not** own `multi_polity_migration`, `institutional_economy`, or `multi_hop_testimony_tracking`. **No new V3 capability flag.** No currency, shop, wage, tax, or market-clearing object.
3. Channel off = prior baseline. With `subjective_valuation` absent, `Give` still moves one item with no return. `Talk` / `Ask` / `Tell` stay delivery-only. `DeclareCommitment` stays unenforced speech. `exact_trajectory_hash` for existing experiments stays the same. No new event, no new command, no valuation ledger.
4. Schema bumps use accepted-set + exact key-set discipline. Never drop accepted V1/V2/V3 versions in the same change that adds a write version.
5. **No global price (locked).** Forbidden config and code aliases include `world_price`, `market_price`, `price_table`, `exchange_rate`, `currency`, `posted_price`, `clearing_price`, `numeraire`. `WorldState` gains no price field. It may gain `exchange_offers` whose fields are parties, item ids, and tick only. An event payload gains no reservation integer. Two agents may store different integers for the same `ItemKind`.
6. **The engine swaps named items, not values (locked).** `NegotiateExchange` `accept` moves the item ids both commands listed. The engine does not read valuation ledgers, and it does not reject a bundle because one party's reservation is higher. A scripted accept of a poor deal still transfers. Cognition is what refuses.
7. **Speech is not a swap (locked).** `offer`, `counteroffer`, and `withdraw` emit history and move nothing. `Talk` is not parsed into an offer. A `Give` in the same tick is a separate command.
8. **One physical vocabulary (locked).** There is no `axe` item kind. The example's axe is one `ItemKind.TOOL` item. Food is one or more `ItemKind.FOOD` items. Do not add an item kind. Do not add a stack quantity on `Item`.
9. **Valuations are owner-scoped and revisable (locked).** Inputs are that owner's needs, scarcity beliefs, inventory, plans, relationships, risk, expected future scarcity, and social obligations. Blank-slate entrants start with empty ledgers. Unknown scarcity is not "zero left".
10. **Preserve v3-02–v3-17 locks:** commitments stay unenforced; blank-slate deny-list gains `subjective_valuations` and `scarcity_beliefs`; corpse custody is possession, not law; no global Culture / LibraryInstitution / `GlobalTechniqueRegistry`; a successful experiment is not knowledge; LLM drafts cannot name physics.

## Goal

Alice and Bob can each decide what one tool is worth in food, disagree, and negotiate with structured offers. Alice's ledger can say the tool is worth 8 food. Bob's can say it is worth 3 food. Nothing in the world stores either number as a price.

If a later offer names bundles both agents will accept, `WorldEngine` moves those items together. The offer, counteroffer, withdrawal, and completed swap stay in the event history so analysis can describe the path and the realized bundles without inventing a market price.

## Design Decisions

### Invariant freeze (non-negotiable)

1. `WorldEngine` does not read valuation ledgers, scarcity beliefs, commitment ledgers, norms, or relationships when it admits `NegotiateExchange` or `Give`.
2. Agents never receive another agent's valuation ledger or scarcity beliefs.
3. `WorldEvent` records remain immutable. Authoritative history is the negotiation events plus the holder changes on `ExchangeCompleted`.
4. Research divergence rows must not bias live cognition.
5. No posted price, currency, or institution.
6. Godot remains read-only. New semantics are labels over negotiation events. No price tag on the map.
7. Runs remain reproducible (explicit seeds, no valuation RNG).
8. Free-text `Talk` is not parsed into an offer. Only `NegotiateExchange` feeds the history.

### Scope split (locked)

| This plan (v3-18) | Deferred |
| --- | --- |
| Private reservation integers per `ItemKind`, in the owner's reference units | A world price, currency, or shared numeraire |
| Scarcity beliefs updated from what that owner sees | A true local-stock fact copied into every agent |
| Structured `offer` / `counteroffer` / `accept` / `withdraw` | Parsing `Talk` into a bargain |
| Atomic multi-item swap when `accept` matches a live offer | `Give` growing a quantity field |
| Objective negotiation history for analysis | Owning `institutional_economy` |
| `runner-config-v40` + replay-v18 / codec v15 only while the channel is on | Alembic `0018+`, `/v2` HTTP, protocol rename |

**Rationale:** `Give` moves one held item and does not ask the recipient. Commitments remember a debt and do not collect it. Nothing lets two agents name both sides of a swap, or remember that one of them wanted eight food while the other wanted three. This plan adds those two pieces and leaves markets to the flag this plan does not own.

### Capability / ownership (locked)

1. **No new V3 flag.** Enabling the channel requires exact `subjective_valuation` on `runner-config-v40` only. Kinship, cultural memory, population lifecycle, commitments, reputation, and social norms are optional neighbors, not prerequisites.
2. **Do not** enable the channel implicitly when commitments, norms, or production are on.
3. **v39 without `subjective_valuation`** stays valid (AT baseline). Schema `v40` always requires `subjective_valuation`.
4. Do **not** implement institutions, currency, kinship knowledge handoff, or cultural inheritance handoff.
5. Other unowned V3 flags still fail closed.
6. When the object is absent: AE–AT bit-identity matches pre-plan for the same roster and seeds. A bare `Give` still creates no return transfer.
7. Optional read-only inputs, ignored by the engine:
   - Needs come from `ObservedSelf` hunger, thirst, and health.
   - Inventory counts come from that owner's observed inventory.
   - Plans come from that owner's goals and recipe beliefs.
   - Relationships come from that owner's `DirectedRelationshipProfile` when a profile exists. Absence → concession 0.
   - Risk comes from fear / mortality appraisal only when that mode is already on. Absence → component 0.
   - Expected future scarcity comes from that owner's causal world model only when that mode is already on. Absence → component 0.
   - Social obligations come from that owner's structured-commitment rows only when `structured_commitments` is already on. Absence → concession 0. Do not read the counterparty's ledger.

### Flag × object gate matrix (locked)

| Config shape | Allowed? | Reject / notes |
| --- | --- | --- |
| Object absent, schema v4–v39 | Yes (off) | Passthrough |
| Object present, schema ≠ v40 | No | `subjective_valuation_requires_v40` |
| Schema v40 without the object | No | `v40_requires_subjective_valuation` |
| Object present, any V3 flag off | Yes | Barter needs no flag |
| Object present, commitments / norms / world-model disabled | Yes | Those components stay 0 |
| Object present, possession / cultural / lifecycle / genealogy / experimentation / commitments on v40 | Yes | Widen those schema allowlists through v40; add v40 to the local `_experiment_schemas` set; keep reject code `bounded_experimentation_requires_v36`; do not require those objects |
| Any forbidden price or currency alias | No | `subjective_valuation_price_forbidden` |
| `mode=disabled` present | No | `subjective_valuation_mode_invalid` — omit the object for off |
| Unowned V3 flag true | No | existing `capability_unimplemented` |

### Runner schema (locked)

Introduce `RUNNER_SCHEMA_VERSION_V40 = "runner-config-v40"`:

- Exact root key set = **v39 accepted roots** ∪ sibling **`subjective_valuation`**. `structured_commitments` and the other v39 siblings stay optional.
- `subjective_valuation` present ⇒ `schema_version == runner-config-v40`.
- Decode v23–v39 synthesizes `subjective_valuation=None`.
- Gate rewrite: cultural, durable, historical-layer, repository, genealogy, experimentation, possession, and structured-commitment allowlists that were extended to v39 in v3-17 also accept v40. Cultural-only still forbids `population_lifecycle`. It allows `subjective_valuation` and `structured_commitments`.
- Default write stays `runner-config-v4` when all V3 flags are off and this object is absent.
- **Write pair:** when the channel is active, `checkpoint_schema_for_production` returns `(EVENT_SCHEMA_REPLAY_V18, "v15")`, higher priority than `structured_commitments_active` (v17/v14). Channel off does not select v18. Add keyword `subjective_valuation_active: bool = False` and pass `config.subjective_valuation is not None` from `src/simulation/runner.py`, `src/simulation/service.py`, and `src/simulation/engine.py`.
- **Loop kwargs:** `_subjective_valuation_loop_kwargs` in `src/simulation/runner.py`, beside `_structured_commitments_loop_kwargs`, passes `subjective_valuation_active`, `horizon_ticks`, and `max_bundle` into `CognitiveLoop`. The world rule context carries `horizon_ticks` and `max_bundle` only.
- **Matrix finalize (Task 14 only):** in `src/experiments/matrix_schema.py`, insert `subjective_valuation_on` immediately before `structured_commitments_on`. Task 1 must **not** edit finalize priority.
- Alembic head stays `0017`. Protocol id stays `observer-protocol-v1`.

### Serialization contract (locked)

Mirror the v39 helper pattern in `runner_serialization.py`:

- v40 root keys = v39 family helper ∪ `{subjective_valuation}` minus optional objects that are absent
- Exact child keyset `_SUBJECTIVE_VALUATION_KEYS`
- `_encode_subjective_valuation` / `_decode_subjective_valuation` with `_require_keys`
- Encode: `schema_version == V40` requires the object
- Decode: v23–v39 → `None`
- DEBUG log `present`, `policy_id`, `horizon_ticks`, `max_bundle` on decode
- Reject forbidden price aliases before key acceptance

### `SubjectiveValuationSpec` (locked)

Root sibling object; omit for off. Exact keys (reject extras / missing):

| Key | Type / values | Role |
| --- | --- | --- |
| `policy_id` | `subjective-valuation-v1` only | Closed policy id |
| `horizon_ticks` | int, `1..64` | How long a proposal stays matchable. Not a price decay |
| `max_bundle` | int, `1..8` | Maximum item ids on each side of one proposal |

No default price, no reference-kind override, no weight table in config. Weights live in code so a config cannot publish a price list.

### Runtime channel flags (locked)

1. `subjective_valuation_active = config.subjective_valuation is not None` at run start.
2. Pass a `SubjectiveValuationRuleContext(allow_negotiate=True, horizon_ticks=..., max_bundle=...)` into `evaluate_operation` only when active. `resolve_tick` threads it through `prepare_action_batch` beside the commitments context. There is no `WorldEngine.tick` method. `None` context ⇒ `NegotiateExchange` rejects with `SUBJECTIVE_VALUATION_CHANNEL_OFF`. Other commands must not start returning that reason.
3. Subjective checkpoint fields `subjective_valuations` and `scarcity_beliefs` (owner id → ledger). Blank-slate keys of the same names. Not SQLAlchemy tables. The same names are fields on `SubjectiveSnapshot`, the loop proposal, and the loop result, matching `structured_commitments`.
4. **No price collection** on `WorldState`. A live proposal is an `exchange_offers` row: unordered pair, proposer, both item-id tuples, and the offer tick. No reservation integer. Codec `v15` journal snapshots include that row, the same way `v13` includes corpse custody. Codecs through `v14` omit it. `evaluate_operation` reads the working `WorldState` only. It does not scan the engine event history.

### Valuation model (locked)

Module `src/agents/cognition/subjective_value.py`. Owner-scoped. Not on `Observation`. Not on `WorldState`.

Reference kind, chosen each appraisal by this owner only:

- Hunger strictly greater than thirst, and hunger > 0 → `FOOD`
- Thirst strictly greater than hunger, and thirst > 0 → `WATER`
- Otherwise → `FOOD`

A reference-kind item is worth **1** reservation unit for that owner. Inventory size does not change that 1. There is no shared numeraire across owners.

For every other `ItemKind`, the reservation is an integer clamped to `0..16`:

| Component | Rule | Off / unknown |
| --- | --- | --- |
| Need | `FOOD`: `hunger // 8`. `WATER`: `thirst // 8`. `MEDICAL`: `(100 - health) // 8`. `TOOL`, `MATERIAL`, `GENERIC`: `0` | Body missing → `0` |
| Inventory | `-min(4, max(0, held_count - 1))` of that kind in the owner's own inventory. The one unit they already hold is not a penalty | `0` |
| Scarcity belief | Others' visible count `0` → `+4`. Count `1` → `+3`. Count `≥ 2` → `0` | No row for that kind → `0`. Do not treat missing as zero stock |
| Plan | `+4` when an active goal or recipe belief names that kind as an input or a required tool | No such plan → `0` |
| Risk | `+2` on `FOOD`, `WATER`, or `MEDICAL` when fear is active or mortality foreclosure is active | Mode off → `0` |
| Expected future scarcity | `+2` when that owner's causal hypothesis or imagined future carries `SubjectiveRiskKind.RESOURCE_LOSS` for that kind | World-model mode off, or no such hypothesis → `0` |

Relationship and social obligation are **concessions**, not item values. They do not change the stored reservation. They apply only when this owner judges a bundle:

- `DEBT` toward the counterparty `≥ 0.4` → `+1`
- `AFFECTION` toward the counterparty `≥ 0.6` → `+1`
- An open own commitment where this owner is the debtor to that counterparty and the kind appears on the bundle → `+1`
- Concession sum clamped to `0..3`

Bundle test, local only: `value(received) + concession >= value(given)`. `value` sums per-item reservations. Reference-kind items contribute 1 each. The engine never runs this test.

The Alice / Bob example is this formula, not a stored price. It does not require the causal world model, fear, or commitments. Those components stay `0`.

- Alice holds the one tool and has a plan that names `TOOL`. Others' visible tool count is `0` → `+4`. Plan → `+4`. Inventory term is `0` because `held_count - 1` is `0`. Tool reservation is `8`. Reference `FOOD` is worth 1. She asks for 8 food items.
- Bob holds no tool and has no such plan. He sees Alice's tool, so others' visible tool count is `1` → `+3`. Tool reservation is `3`. He offers at most 3 food items. Concession `0`.
- Those two bundles fail the private test both ways. No `ExchangeCompleted`.

Each stored row:

| Field | Meaning |
| --- | --- |
| `item_kind` | Closed `ItemKind` |
| `reference_kind` | This owner's unit at appraisal time |
| `reservation` | Integer `0..16`. Always `1` when `item_kind == reference_kind` |
| `components` | Closed tokens with the integer each component contributed |
| `tick` | Appraisal tick |
| `counterparty_id` | Set only on a judgment row. Empty on a kind row |

Keep the latest kind row per `item_kind` plus one judgment row per proposal this owner answered. Cap judgment rows at `max_bundle * 4` (at most 32). Drop the oldest judgment. Do not drop kind rows.

### Scarcity beliefs (locked)

Module `src/agents/cognition/scarcity_beliefs.py`. Owner-scoped.

A row is `item_kind`, `believed_local_count` (`0..64`), `location_id`, `tick`. `believed_local_count` is how many items of that kind this owner can see at the current location and does not hold. That includes ground items and, when the channel is on, other bodies' held items from the observation. It does not include this owner's own inventory. Leaving the location does not erase the row. The next visit overwrites it. A newborn has no rows. A missing row is not count `0`. Hidden items in another location cannot change the count. The belief may be wrong. Do not copy another owner's rows.

### Negotiation command (locked)

New command `NegotiateExchange` (command count **38**):

| Field | Rule |
| --- | --- |
| `counterparty_id` | Living body, distinct from the actor, same location |
| `act` | `offer` \| `counteroffer` \| `accept` \| `withdraw` |
| `give_item_ids` | Tuple of distinct item ids, length `0..max_bundle`. Empty only when `act=withdraw` |
| `take_item_ids` | Tuple of distinct item ids, length `0..max_bundle`. Empty only when `act=withdraw` |

Reject when:

- An id appears on both sides, or twice on one side
- `offer` or `counteroffer` has an empty side (a gift stays `Give`)
- Length exceeds `max_bundle`
- `give_item_ids` are not held by the actor, or `take_item_ids` are not held by the counterparty, except `withdraw`
- Either body is dead, or they are apart
- Either side would exceed carry capacity after the swap (checked on `accept` only)
- `accept` or `counteroffer` has no live proposal, or the live proposal is older than `horizon_ticks`
- `accept` bundles are not the swap of the live proposal (speaker give = proposal take, speaker take = proposal give)
- `withdraw` is not from the actor who made the live proposal

Live proposal = the `exchange_offers` row for the unordered pair whose tick is inside the horizon. `offer` and `counteroffer` write that row and move no items. `withdraw` and `ExchangeCompleted` delete it. A `Give` does not delete it. A failed `accept` does not delete it. An expired row is not live and emits nothing. The next `offer` replaces it. While one row is live, the counterparty uses `counteroffer` or `accept`. A second `offer` rejects with `EXCHANGE_OFFER_OPEN`. The same item may sit in two pairs' rows. The first successful `accept` moves it. The other `accept` fails `NOT_HELD` and moves nothing.

Same-tick matching follows submission order inside `prepare_action_batch`. An `accept` sees an `offer` from that tick only when the offer is earlier in the sequence. Cognition reads the previous tick's observation, so a proposer answers on a later tick. Scripted arms that put both commands in one tick must submit the offer first.

`offer` and `counteroffer` emit `ExchangeProposed` and move nothing. `withdraw` emits `ExchangeWithdrawn` and moves nothing. `accept` emits `ExchangeCompleted` and, in the same mutation, moves every named item. If any hold or capacity check fails, move none of them.

`ExchangeCompleted` carries actor id, counterparty id, both item-id tuples, and both item-kind tuples looked up from world state. It does not carry reservation integers.

`Give` stays one item, no consent, no bundle.

### Perception (locked)

`ExchangeProposed`, `ExchangeWithdrawn`, and `ExchangeCompleted` are colocated public occurrences.

- Actor, counterparty, and a colocated witness receive act, both item-id tuples, and both item-kind tuples.
- An agent in another location receives nothing.
- Nobody receives a reservation, a component token, or a scarcity count.
- `target_id_for_details` returns `counterparty_id`.

Other agents' inventories stay omitted when the channel is off (`other_inventory` is `OMITTED`). When the channel is on, each colocated observation gains `exchange_visible_holdings`: body id, item id, kind, and load for items held by other bodies at that location. No health, no hunger, no reservation. Channel off adds no observation keys, so existing observations stay the same. The first offer uses those holdings. It does not wait for an exchange event to reveal item ids.

### Cognition policy (locked)

`propose_exchange_command` runs only when the channel is on, after the commitment proposer and before `ActionPlan` is built.

- Channel off returns the incoming command unchanged.
- If the observation contains a live proposal naming this owner as counterparty, accept when the bundle test passes. Otherwise counter with concrete visible item ids that move the food side to `min(max_bundle, reservation)` of the tool, or withdraw when the counterparty does not hold enough visible reference items and this owner holds nothing else to add.
- Do not emit `Give` as the payment. Do not emit `Attack`. Do not parse `Talk`.
- A counteroffer lists item ids, never a reservation integer, on the command.

### Analytical conventions (locked)

`src/analysis/subjective_value.py`. Pure functions over detached events plus optional detached ledgers. `WorldEngine` does not import this module.

| Field | Meaning |
| --- | --- |
| `path` | Offer, counteroffer, withdraw, and completed events. This is what was said and what moved |
| `reservations` | One row per owner ledger. Missing ledger → `unformed`, not "agreed" |
| `divergent` | True when two owners' tool reservations differ |
| `realized_bundle` | Kind counts stored on the metric row itself. Not a food-per-tool price computed and then stored under another name |
| `world_price` | Always absent. A present price field is a test failure |
| `institution` | Always `none` |

The Alice 8 / Bob 3 case is `divergent` and has no `ExchangeCompleted`. Analysis must not average 8 and 3 into a price.

### Observer (locked)

Add exactly three semantic types, protocol id unchanged:

- `EXCHANGE_PROPOSED`
- `EXCHANGE_WITHDRAWN`
- `EXCHANGE_COMPLETED`

The tuple length is 58 today. Three additions make **61**. Sweep every `len(SEMANTIC_EVENT_TYPES) == 58` pin.

Command count becomes **38** (`NegotiateExchange` only). `Give` is not duplicated. Counteroffer reuses `ExchangeProposed` with `act=counteroffer`.

### Experiment AU (locked)

Id `subjective_exchange@1`. Off `OFF_GATE_MATRIX_EXPERIMENT_IDS` / V1 gate. Four arms, same seed and roster:

| Arm | Setup | Assertion |
| --- | --- | --- |
| `au-channel-off` | no object; scripted `Give` of one food item | item moves; no exchange event; no ledger field; hash equals the pre-plan fixture |
| `au-divergent-reservation` | v40; Alice holds one tool and has a plan that names `TOOL`; Bob holds at least eight food items and no tool plan; one colocated observation writes scarcity before anyone offers; the proposer runs on the next tick | no `ExchangeCompleted`; events may show offer and counteroffer; event payloads have no reservation integer; ledgers still show 8 and 3; world-model mode stays off |
| `au-agreed-swap` | v40; both reservations overlap on one tool for 4 food items; scripted offer and accept | one `ExchangeCompleted`; tool and those four food items change holders together; a broken accept (one food already given away) moves nothing |
| `au-history` | v40; scripted offer, counteroffer, then overlapping accept | the three events exist in order; metric `realized_bundle` counts kinds; `world_price` stays absent; `institution` is `none` |

Default batches do not enable AU. `au-divergent-reservation` may use the proposer. `au-agreed-swap` and `au-history` script the commands so the arm does not depend on a search.

### Metric families (locked)

Three siblings. Pin `METRIC_FAMILY_COUNT` from 77 to **80**. Empty harvest when the channel is off.

| Family id | Reads | Does not |
| --- | --- | --- |
| `exchange_reservation_divergence` | each owner's reservation integer and component tokens, stored as those fields | average them into a price |
| `exchange_negotiation_path` | offer, counteroffer, withdraw, and complete counts, stored as those counts | treat a withdrawn offer as a transfer |
| `exchange_realized_bundles` | per-kind counts on completed swaps, stored as those counts | store a food-per-tool ratio under the name `price` |

Research UI Analytics badges for these three ids only, overlay kind `research_inference`. Badge titles say "reservation" and "bundle", not "price".

## Docs (mandatory checkpoint)

`/aif-implement` must route this through `/aif-docs` before done:

- `docs/social-communication.md` — structured barter versus `Give`, `Talk`, and unenforced commitments
- `docs/cognition-runtime.md` — valuation inputs, scarcity beliefs, concessions, disagreement
- `docs/analysis-metrics.md` — three families, realized bundles are not prices
- `docs/architecture.md` — v40, replay-v18/codec v15 only when active, command 38, semantic count 61
- `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/ROADMAP.md` — M7 note; `institutional_economy` still unowned; no world price

Docs must not describe a reservation as a market price.

## Commit Plan

- **Commit 1** (after tasks 1–4): `feat: add subjective valuation config on runner-config-v40`
- **Commit 2** (after tasks 5–7): `feat: swap agreed item bundles without storing a price`
- **Commit 3** (after tasks 8–11): `feat: let agents value goods and negotiate bundles`
- **Commit 4** (after tasks 12–14): `feat: record exchange disagreement and realized bundles`
- **Commit 5** (after task 15): `docs: describe barter without a world price`

## Tasks

### Phase 1: Schema

- [x] Task 1: Add `RUNNER_SCHEMA_VERSION_V40`, `SubjectiveValuationSpec` (`policy_id`, `horizon_ticks`, `max_bundle`), `SimulationRunnerConfig.subjective_valuation`, exact encode/decode, forbidden-price alias frozenset, and the reject codes in the flag×object matrix. Decode v23–v39 synthesizes `None`. Widen cultural, durable, historical-layer, repository, genealogy, experimentation, possession, and structured-commitment schema allowlists through v40 without requiring those objects. Add v40 to the local `_experiment_schemas` set in `SimulationRunnerConfig` post-init and keep reject code `bounded_experimentation_requires_v36`. Cultural-only still forbids `population_lifecycle`. Do not edit matrix finalize priority (Task 14). Do not add a V3 flag. Do not add a weight table or a reference-kind key.
  - Deliverable: Round-trip tests; rejects for v40 without the object, object on v39, `horizon_ticks` outside `1..64`, `max_bundle` outside `1..8`, `mode=disabled`, and each forbidden price alias; v39 commitment config still loads; v40 with only `subjective_valuation` loads with all V3 flags off.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `tests/unit/test_subjective_valuation_spec.py`
  - Logging: DEBUG decode with `present`, `policy_id`, `horizon_ticks`, and `max_bundle` only; INFO/raise stable reject codes; never log a reservation at INFO
  - Depends on: none

- [x] Task 2: Add `EVENT_SCHEMA_REPLAY_V18` and codec `v15`. Add `subjective_valuation_active: bool = False` to `checkpoint_schema_for_production` and select `(EVENT_SCHEMA_REPLAY_V18, "v15")` only when that flag is true, ahead of structured commitments v17/v14. Pass `config.subjective_valuation is not None` from `src/simulation/runner.py`, `src/simulation/service.py`, and `src/simulation/engine.py`. Store the flag, `horizon_ticks`, and `max_bundle` on `WorldEngine` (`__init__`, both snapshot-restore paths beside `_structured_commitments_horizon`, and `_subjective_valuation_rule_context`). Thread `subjective_valuation_context` into `prepare_action_batch` beside `structured_commitments_context`. `resolve_tick` is the admission path. Channel off keeps the previous pair. Accept `ExchangeProposed`, `ExchangeWithdrawn`, and `ExchangeCompleted` only on v18. Replay-v17 decode rejects those kinds. Add `_subjective_valuation_loop_kwargs` beside `_structured_commitments_loop_kwargs` and pass `subjective_valuation_active`, `horizon_ticks`, and `max_bundle` into `CognitiveLoop`.
  - Deliverable: Version-selection tests for channel off, commitments on without this object, and this object on (with and without commitments). Unknown kind on v17 fails closed. A v40 config reaches the loop with the spec horizon and bundle cap. A restored engine keeps the flag and the horizon. A v39 config leaves the new keyword false.
  - Files: `src/simulation/serialization.py`, `src/simulation/persistence.py`, `src/simulation/compatibility.py`, `src/simulation/runner.py`, `src/simulation/service.py`, `src/simulation/engine.py`, `src/world/_operations.py`, `src/agents/cognition/loop.py`, `src/agents/cognition/configuration.py`, `src/world/events.py`, `tests/unit/test_subjective_valuation_replay_schema.py`
  - Logging: INFO `checkpoint_schema_selected` with replay version and codec; DEBUG channel flag, `horizon_ticks`, and `max_bundle` when active; ERROR on kind/schema mismatch with the kind name only
  - Depends on: 1

- [x] Task 3: Make codec `v15` a superset of codec `v14`. Every journal, engine, and persistence allowlist that currently ends at `v14` also accepts `v15`. `structured_commitments_checkpoint_payload` and its decoder accept `v14` or `v15`, and still reject the key on `v13` and below. Do the same for any other `codec == "v14"` gate that would otherwise drop a v14 payload when the write pair is v15. Do not drop lifecycle, kinship, repositories, corpse custody, or commitment ledgers from a v15 snapshot. Add `v15` beside each existing `v14`. Leave unrelated duplicate entries alone unless ruff requires a change.
  - Deliverable: A checkpoint with both `structured_commitments` and `subjective_valuation` round-trips commitments, corpse custody, lifecycle records, kinship edges, and repositories on codec `v15`. A `v14` snapshot still round-trips commitments and still has no valuation keys. A `v13` payload that contains `structured_commitments` still fails closed.
  - Files: `src/simulation/journal.py`, `src/simulation/engine.py`, `src/simulation/persistence.py`, `src/simulation/serialization.py`, `tests/unit/test_subjective_valuation_replay_schema.py`
  - Logging: DEBUG `codec_superset` with the codec version when a v14 payload is written on v15; ERROR with the reject code when an older codec carries a forbidden key
  - Depends on: 2

- [x] Task 4: Add event dataclasses `ExchangeProposed`, `ExchangeWithdrawn`, and `ExchangeCompleted` with actor id, counterparty id, act, and both item-id tuples. `ExchangeCompleted` also carries both item-kind tuples. Add them to the `EventDetails` union, `require_event_details`, `target_id_for_details`, and the replay `match` arms. Do not add a reservation field. Add `exchange_offers` on `WorldState` and `rebuild_world_state` (unordered pair, proposer, both item-id tuples, tick). No reservation field. Replay of `ExchangeProposed` writes the row and changes no holders. Replay of `ExchangeWithdrawn` deletes the row. Replay of `ExchangeCompleted` deletes the row and applies the holder swap. Codec `v15` journal snapshots include `exchange_offers`, following the corpse-custody snapshot pattern. Codecs through `v14` omit the key. Engine snapshot restore rebuilds the rows.
  - Deliverable: Project a proposal and assert inventories match the pre-image and one offer row exists. Project a completion and assert both sides' holders change and the row is gone. A v15 snapshot round-trips the offer row and has no price field. A folded v17 log has no exchange kind. A v14 snapshot has no `exchange_offers` key.
  - Files: `src/world/events.py`, `src/world/_state.py`, `src/world/_replay.py`, `src/simulation/journal.py`, `src/simulation/engine.py`, `tests/unit/test_exchange_projection.py`
  - Logging: DEBUG `exchange_projected` with act and both tuple lengths; DEBUG `exchange_offer_stored` with pair ids and tick; no reservation integers
  - Depends on: 3

<!-- Commit checkpoint: tasks 1–4 -->

### Phase 2: Agreed transfer

- [x] Task 5: Add command `NegotiateExchange` (command count 38) and rule evaluation under `SubjectiveValuationRuleContext`. `resolve_tick` passes that context through `prepare_action_batch`, or `None` when the object is absent. Enforce the command table: living colocated parties, distinct ids, bundle bounds, held items, no gift-shaped offer, live-proposal matching against `exchange_offers` on the working state, horizon, and all-or-nothing capacity using `Item.load` and `effective_carry_capacity`. `offer` and `counteroffer` emit `ExchangeProposed`, write the row, and move nothing. `withdraw` emits `ExchangeWithdrawn`, deletes the row, and moves nothing. `accept` emits `ExchangeCompleted`, deletes the row, and moves every named item or none. A `Give` leaves the row in place. A failed hold or capacity check moves nothing and leaves the row. An expired row is not live. The next `offer` replaces it and emits no withdraw. A same-tick `accept` matches only an earlier submission in that batch. Context `None` rejects with `SUBJECTIVE_VALUATION_CHANNEL_OFF` only for this command. Wire the operation arm in `src/world/_operations.py`, command encode/decode in `src/simulation/serialization.py`, and causal-debugger kind maps in `src/simulation/causal_debugger.py`. The rule context must not contain a ledger. `Give` behavior stays unchanged.
  - Deliverable: Tests for an offer that does not move items and does write a row; an accept that swaps one tool and four food items and deletes the row; a failed accept that moves nothing and keeps the row; a `Give` of an offered item that leaves the row; channel-off command rejected; expired row replaced by a new offer; empty-side offer rejected; two pairs listing the same item, with the second accept failing `NOT_HELD`; same-tick accept ignored when it is submitted before the offer; command registry includes the new command exactly once; a serialized command round-trips. Passing a valuation ledger into the rule context is a type error.
  - Files: `src/world/actions.py`, `src/world/subjective_value.py`, `src/world/_rules.py`, `src/world/_operations.py`, `src/simulation/engine.py`, `src/simulation/serialization.py`, `src/simulation/causal_debugger.py`, `tests/unit/test_negotiate_exchange.py`
  - Logging: INFO `exchange_completed` with both tuple lengths; INFO `exchange_proposed` with act; DEBUG reject reason; never log a reservation
  - Depends on: 4

- [x] Task 6: Perception for the three exchange events, plus channel-on holdings. Colocated actor, counterparty, and witnesses receive act, item ids, and item kinds. Remote agents receive no occurrence. Do not attach a reservation, a component list, a scarcity count, or another agent's ledger. When the channel is on, add `exchange_visible_holdings` on the colocated observation: body id, item id, kind, and load for items held by other bodies at that location. Channel off adds no observation keys and no exchange occurrence.
  - Deliverable: Three colocated agents see the same bundle tokens; an agent in another location sees none; channel off emits no exchange occurrence and no holdings field; channel on lists the counterparty's food item ids and kinds without health or hunger; the observation has no reservation field.
  - Files: `src/world/observations.py`, `src/world/_perception.py`, `src/world/events.py`, `src/simulation/engine.py`, `tests/unit/test_exchange_perception.py`
  - Logging: DEBUG `exchange_occurrence` with act, audience role, and tuple lengths; DEBUG `exchange_holdings_visible` with holding count; no reservation at INFO
  - Depends on: 5

- [x] Task 7: Observer semantics `EXCHANGE_PROPOSED`, `EXCHANGE_WITHDRAWN`, and `EXCHANGE_COMPLETED`. Protocol id unchanged. Map the kinds in `SEMANTIC_TYPE_BY_KIND` and the causal-debugger semantic map. Godot stays read-only (no price overlay). Length is 58 today and 61 after. Sweep `len(SEMANTIC_EVENT_TYPES) == 58` in the observer, experiment-perception, and v3 regression tests that pin it.
  - Deliverable: Semantic tuple length is 61; a fixture completion exports the new label; no remaining `== 58` pin.
  - Files: `src/observer/version.py`, `src/observer/contracts.py`, `src/simulation/causal_debugger.py`, and the pin files found by the sweep
  - Logging: DEBUG `observer_semantic_mapped` with kind and semantic; no payload bodies
  - Depends on: 5

<!-- Commit checkpoint: tasks 5–7 -->

### Phase 3: Private value and negotiation

- [x] Task 8: Add owner-scoped scarcity-belief and valuation ledger types and the empty constructors. Export them from the cognition package. Add `scarcity_beliefs` and `subjective_valuations` to `BLANK_SLATE_SUBJECTIVE_STORES`. Add both fields on `SubjectiveSnapshot`, the loop proposal, and the loop result, beside `structured_commitments`. Checkpoint fields round-trip only on codec v15; absent on older codecs. An older codec that still carries either key fails with `subjective_valuation_requires_codec_v15`. A v15 checkpoint that also has commitments still carries those commitments (Task 3).
  - Deliverable: Blank-slate assert fails if a newborn ledger is non-empty; codec v14 checkpoint has neither valuation field and still has commitments when that channel was on; codec v15 round-trips two owners' different tool reservations; a missing scarcity row is distinct from count 0.
  - Files: `src/agents/cognition/scarcity_beliefs.py`, `src/agents/cognition/subjective_value.py`, `src/agents/cognition/__init__.py`, `src/agents/cognition/models.py`, `src/agents/cognition/contracts.py`, `src/simulation/new_agent_initialization.py`, `src/simulation/run_control.py`, `src/simulation/serialization.py`, `tests/unit/test_subjective_value_ledger.py`
  - Logging: DEBUG `valuation_stored` with owner id, item kind, and reservation; DEBUG `scarcity_belief_stored` with item kind and count; INFO `blank_slate_asserted` includes the new stores; never log another owner's reservation
  - Depends on: 3

- [x] Task 9: Implement the appraisal function from the valuation table. Reference kind follows hunger versus thirst. Reference items stay worth 1. Other kinds clamp to `0..16`. Inventory uses `-min(4, max(0, held_count - 1))`. Scarcity uses others' visible count: `0 → +4`, `1 → +3`, `≥ 2 → 0`, missing row → `0`. Plan is `+4`. Risk and expected future scarcity stay `+2` only when those modes are already on. Concession is separate and capped at 3. Update scarcity rows from ground items plus `exchange_visible_holdings`, excluding items this owner holds.
  - Deliverable: Known-answer tests for Alice's tool reservation 8 and Bob's tool reservation 3 from the design section, with world-model mode off; the one tool Alice holds does not reduce her reservation; reference food stays 1 while she also holds eight food items; a missing scarcity row adds 0 and a zero row adds 4; a count of 1 adds 3; world-model off adds 0 expected scarcity; commitment off adds 0 obligation concession; a child starts with no rows.
  - Files: `src/agents/cognition/subjective_value.py`, `src/agents/cognition/scarcity_beliefs.py`, `src/agents/cognition/loop.py`, `tests/unit/test_subjective_value_appraisal.py`
  - Logging: DEBUG `valuation_appraised` with item kind, reservation, and component tokens; DEBUG `scarcity_belief_updated` with location id and count; never log component integers at INFO
  - Depends on: 6, 8

- [x] Task 10: Wire appraisal into the loop after observation and before deliberation. Store the latest kind row per item kind. Store a judgment row when this owner answers a proposal. Enforce the judgment cap. Carry both ledgers on the loop proposal and result into `agent_runtime`, and restore them from the v15 checkpoint, matching `_commit_structured_commitments`. Do not copy rows onto a new agent. Do not put rows on `Observation`.
  - Deliverable: Tests for checkpoint restore of two different reservations; over-cap judgment drop keeps kind rows; blank child after a parent appraisal; channel off writes neither store; the loop result exposes both ledgers.
  - Files: `src/agents/cognition/loop.py`, `src/agents/cognition/models.py`, `src/simulation/agent_runtime.py`, `src/agents/cognition/subjective_value.py`, `tests/unit/test_subjective_value_bind.py`
  - Logging: DEBUG `valuation_bound` with owner id and kind-row count; DEBUG `valuation_judgment_dropped` when over cap; never log the counterparty's ledger
  - Depends on: 6, 9

- [x] Task 11: Deterministic proposer used only when the channel is on. Read this owner's ledgers from `loop_input.snapshot`. Accept a perceived proposal when `value(received) + concession >= value(given)`. Otherwise counter with item ids from `exchange_visible_holdings` toward `min(max_bundle, reservation)` reference items, or withdraw when that counter cannot be filled. Do not put a reservation on the command. Do not emit `Give` or `Attack`. Channel off leaves the existing command ranking unchanged, including the commitment proposer. The call sits after `propose_commitment_command` and before `ActionPlan`.
  - Deliverable: Tests for Alice refusing Bob's 3-food offer and countering toward 8 when eight food item ids are on `exchange_visible_holdings`; Bob refusing an 8-food ask; accept when both reservations overlap; no automatic `Give`; channel-off ranking unchanged; no `Attack`.
  - Files: `src/agents/cognition/subjective_value.py`, `src/agents/cognition/deliberation.py`, `tests/unit/test_exchange_proposer.py`
  - Logging: DEBUG `exchange_proposal` with command tag and act; INFO only when a proposal is selected; log tuple lengths, never reservation integers, at INFO
  - Depends on: 6, 10

<!-- Commit checkpoint: tasks 8–11 -->

### Phase 4: Measurement

- [x] Task 12: Implement `classify_exchange` in `src/analysis/subjective_value.py` from the analytical conventions table. Inputs are detached events plus optional ledger snapshots. Output separates path tokens from per-owner reservations. Missing ledgers yield `unformed`. `world_price` is absent. `institution` is `none`. A completed event contributes `realized_bundle` kind counts stored as those counts, not a price.
  - Deliverable: Known-answer tests for the 8-versus-3 divergence with no completion, an overlapping completion, a withdrawn path, channel-off empty list, and a fixture that fails if a price field is present.
  - Files: `src/analysis/subjective_value.py`, `src/analysis/__init__.py`, `tests/unit/test_subjective_value_classify.py`, `tests/architecture/test_v3_subjective_value_isolation.py`
  - Logging: DEBUG `exchange_classified` with `divergent` and event counts; no agent rosters at INFO
  - Depends on: 7, 11

- [x] Task 13: Add the three metric families and pin `METRIC_FAMILY_COUNT` to 80. Store each owner's reservation integer on `exchange_reservation_divergence` and per-kind counts on `exchange_realized_bundles`. Do not store a derived food-per-tool ratio as `price`. Sweep unit tests that assert `== 77`. Assemble only when the spec was present. Empty harvest when the object is absent. Research UI Analytics badges for the three family ids, kind `research_inference`, same pattern as commitment badges. Badge copy must not say "price". No new graph panel.
  - Deliverable: Known-answer metric rows that include the reservation integers 8 and 3 and the kind counts; channel-off empty; badge test; no remaining `METRIC_FAMILY_COUNT == 77` pin; a row that contains a `price` field fails the test.
  - Files: `src/analysis/specifications.py`, `src/analysis/subjective_value_metrics.py`, `src/analysis/metric_service.py`, `src/experiments/composition.py`, `src/experiments/collectors.py`, `clients/research-ui/src/epistemic.ts`, `clients/research-ui/src/views/AnalyticsPanel.svelte`, `clients/research-ui/src/epistemic.test.ts`, tests that pin the family count
  - Logging: DEBUG `subjective_value_metrics_assembled` with family ids and row counts; UI badge titles say reservation or bundle
  - Depends on: 12

- [x] Task 14: Register off-gate Experiment AU (`subjective_exchange@1`) with the four arms in the design section. `au-divergent-reservation` gives Bob at least eight food items, lets one colocated observation write scarcity beliefs, and runs the proposer on the following tick. World-model mode stays off. Insert `subjective_valuation_on` in `src/experiments/matrix_schema.py` immediately before `structured_commitments_on`. Add the id to `OFF_GATE_MATRIX_EXPERIMENT_IDS`. Export the builder. AU stays off the V1 gate. `au-channel-off` hash matches the pre-plan fixture. `au-agreed-swap` proves a failed accept moves nothing. `au-divergent-reservation` proves the ledgers still hold 8 and 3 after negotiation. Scripted same-tick arms submit the offer before the accept.
  - Deliverable: Catalog tests for each arm; V1 regression gate and `test_v2_scientific_invariants` green with V3 flags off and without `subjective_valuation`; `au-history` shows offer, counteroffer, and completion in order with `world_price` absent.
  - Files: `src/experiments/catalog.py`, `src/experiments/__init__.py`, `src/experiments/matrix_schema.py`, `tests/unit/test_experiment_au.py`
  - Logging: INFO `experiment_arm_start` with arm id and schema version; DEBUG `subjective_valuation_active`
  - Depends on: 5, 11, 13

<!-- Commit checkpoint: tasks 12–14 -->

### Phase 5: Docs

- [x] Task 15: Docs checkpoint listed in the Docs section. Confirm Alembic head `0017`, protocol id unchanged, command count 38, semantic count 61, write pair v18/v15 only when the channel is on, codec v15 still carries v14 payloads, and `exchange_offers` has no reservation field. Run `ruff check` on the changed Python set before this commit.
  - Deliverable: Doc updates; architecture isolation green; ruff clean on the changed set.
  - Files: `docs/architecture.md`, `docs/social-communication.md`, `docs/cognition-runtime.md`, `docs/analysis-metrics.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/ROADMAP.md`
  - Logging: none in docs; docs must say a reservation is a private belief and a completed event lists items, not a price
  - Depends on: 14

<!-- Commit checkpoint: task 15 -->
