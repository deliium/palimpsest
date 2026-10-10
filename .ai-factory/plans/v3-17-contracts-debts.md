# Implementation Plan: V3-17 Promises, Contracts, and Debts

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-10
Improved: 2026-10-10 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M7 — V3 Generational Civilization"
Rationale: Adds owner-scoped structured commitments so agents can remember promises, exchanges, debts, services, and conditions differently, while the world still does not enforce them.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] mode=ultra treated as full (richer plan); remaining args describe the feature
INFO [aif-plan] resolved plan file: .ai-factory/plans/v3-17-contracts-debts.md (format=slug)
INFO [aif-plan] plan name prefix v3- applied per user request; suggested stem `v3-17-contracts-debts`; git.create_branches=false so stem is description slug (branch-derived naming disabled)
INFO [aif-plan] RESEARCH.md absent; research_influenced_plan=false
INFO [aif-plan] plan_default_milestone=auto would surface M6 first; scope is explicitly v3-17 under M7 so linkage uses M7
INFO [aif-improve] refined 2026-10-10: channel-on Given item_kind facts; two-leg match; absolute debtor_id/creditor_id; due-kind and report rules; relationship signal direction; note_remembered_reliability and note_reciprocal_commitment_evidence; checkpoint callers and loop kwargs; WRITE_MEMORY link; divergent arm forgets traces; no identity-aspect write

## Compatibility contract

This plan extends social life with explicit structured commitments. It does **not** own a new `V3CapabilityFlags` slot, and it does **not** install a contract the engine collects.

1. V1/V2 invariants intact. `WorldEngine` remains the only objective mutation authority. Agents receive immutable per-agent `Observation` / `Perspective` only. `WorldEvent` records remain immutable and append-only. Subjective terms stay outside the objective fold. Godot remains read-only. Deterministic replay continues. No scripted `debts_must_be_paid` / `promises_bind` / `institution_enforces` outcomes.
2. Flag ownership unchanged: keep `cultural_historical_memory`, `generational_population`, and `kinship_inheritance` owned. Do **not** own `multi_polity_migration`, `institutional_economy`, or `multi_hop_testimony_tracking`. **No new V3 capability flag.** Institutions stay deferred until a later plan owns that flag.
3. Channel off = prior baseline. With `structured_commitments` absent, `Give` still moves one item and records no return. `Talk` / `Ask` / `Tell` stay delivery-only. Identity `COMMITMENT` stays a self-belief about the owner's own goal. Relationship `DEBT` stays a scalar. Norm return windows stay private pattern beliefs. `exact_trajectory_hash` for existing experiments stays the same. No new event, no new command, no ledger.
4. Schema bumps use accepted-set + exact key-set discipline. Never drop accepted V1/V2/V3 versions in the same change that adds a write version.
5. **No contract enforcement (locked).** The engine never reads ledgers, kinship, norms, reputation, or group membership when it admits `Give`, `Help`, `Feed`, `Transport`, or `DeclareCommitment`. Forbidden config and code aliases include `enforced_contract`, `auto_collect`, `breach_damage`, `contract_law`, `shared_ledger`, `canonical_terms`, `court`, `institution_enforces`, `obligation_rejects_command`.
6. **Speech is not a transfer (locked).** `DeclareCommitment` emits a public assertion. It does not move items, change health, reject a later command, or create a world-owned agreement id. A `Give` in the same tick is a separate command. Saying "I will bring wood later" does not require holding a material item, and it does not schedule one.
7. **One physical vocabulary (locked).** There is no `wood` item kind. The example's wood is `ItemKind.MATERIAL`. Do not add an item kind in this plan.
8. **Terms are owner-scoped and revisable (locked).** Closed kinds: `promise`, `future_exchange`, `debt`, `service_obligation`, `conditional_agreement`. None is seeded as truth. Blank-slate entrants start with an empty ledger. Two owners may store different parties, terms, quantities, and due conditions for the same public speech. Identity `IdentityAspect.COMMITMENT` is not this ledger and must not be replaced by it.
9. **Consequences are social, not physical (locked).**
    - Memory: each adopted interpretation links to that owner's traces. Forgetting follows those traces.
    - Reputation: optional reliability support when `ReputationMode` is already `DETERMINISTIC`. Channel code stays an existing reputation channel.
    - Relationships: optional revisions through existing `RESOURCE_RECEIVED`, `RESOURCE_GIVEN`, `CORROBORATION_RECEIVED`, and `CONTRADICTION_RECEIVED` signals. No new relationship dimension.
    - Norms: optional evidence on an existing `RECIPROCAL_EXCHANGE` belief when `SocialNormMode` is already `DETERMINISTIC`. Do not seed a norm.
    - Sanctions: subjective tokens only (`none`, `criticism`, `shun`, `retaliation_considered`). `retaliation_considered` does not enqueue `Attack`. No new damage rule.
    - Institutions: not implemented. Analysis must not emit `institution_formed`.
10. **Preserve v3-02–v3-16 locks:** blank-slate deny-list gains only `structured_commitments`; closed Observation `lifecycle` unchanged; ELDER ≠ leader; related ≠ affection or obligation; no parent→caregiver hardwiring; no global Culture / LibraryInstitution / `GlobalTechniqueRegistry`; durable marks ≠ truth; historical layers and technique lifecycle stay analysis-only; a successful experiment is not knowledge; LLM drafts cannot name physics; kinship cultural / knowledge handoff stays deferred; corpse custody is physical possession and doctrines are not law. Author death still does not delete records, repositories, or practical-knowledge audits.
11. **`api` must not import `analysis`.** `simulation` and `persistence` must not import `analysis`. `world` must not import `agents` or `analysis`. `world` must not import the commitment ledger.

## Goal

Agents can speak a closed commitment — a promise, a future exchange, a debt, a service obligation, or a conditional agreement — and each party can remember the terms, the due condition, and what happened next.

The running example is: one agent gives food now, and someone says material will come later. The food moves only because of `Give`. The later material moves only because of a later `Give`. Each owner may mark that pair fulfilled, only partly fulfilled, violated, disputed, or forgotten. Another owner who heard the same speech may disagree. The world does not pick a winner and does not collect the debt.

## Design Decisions

### Invariant freeze (non-negotiable)

1. `WorldEngine` does not read commitment ledgers, norm ledgers, reputation, relationship debt, or kinship when resolving commands.
2. Agents never receive another agent's commitment ledger.
3. `WorldEvent` records remain immutable; authoritative history stays append-only.
4. Research divergence rows must not bias live cognition.
5. No scripted repayment, breach damage, or shared term sheet.
6. Godot remains read-only. New semantics are labels over speech events. No map chrome that draws a legal creditor.
7. Runs remain reproducible (explicit seeds, no contract RNG).
8. Free-text `Talk` is not parsed into a commitment. Only `DeclareCommitment` feeds the ledger.

### Scope split (locked)

| This plan (v3-17) | Deferred |
| --- | --- |
| Public `DeclareCommitment` with closed kind, act, term, and due tokens | Natural-language offers parsed from `Talk` |
| Owner-scoped interpretations that may diverge | One canonical agreement row on `WorldState` |
| Fulfillment, partial fulfillment, violation, dispute, and forgetting as ledger statuses | Engine rejection of commands after a due tick |
| Links from an interpretation to that owner's memory traces | A new memory store or distortion code |
| Consequence requests into existing relationship, reputation, norm, and sanction paths | Institutions, courts, fines, or `institutional_economy` |
| `runner-config-v39` + replay-v17 / codec v14 only while the channel is on | Alembic `0018+`, `/v2` HTTP, protocol rename |
| Experiment AT off the V1 gate | Owning `multi_polity_migration` or `multi_hop_testimony_tracking` |

**Rationale:** Today a commitment is either an identity self-belief (`IdentityAspect.COMMITMENT` about the owner's goal) or a private pattern (`NormWindow` / scalar `RelationshipDimension.DEBT`). Neither names both parties, a term, and a due condition. `Give` moves one item and stores no return. This plan adds the missing subjective record and a public speech act, and leaves collection to whatever memory, reputation, relationships, norms, and later institutions already do.

### Capability / ownership (locked)

1. **No new V3 flag.** Enabling the channel requires exact `structured_commitments` on `runner-config-v39` only. Kinship, cultural memory, population lifecycle, reputation, and social norms are optional neighbors, not prerequisites.
2. **Do not** enable the channel implicitly when norms, reputation, or identity are on.
3. **v38 without `structured_commitments`** stays valid (AS baseline). Schema `v39` always requires `structured_commitments`.
4. Do **not** implement institutions, kinship knowledge handoff, or cultural inheritance handoff.
5. Other unowned V3 flags still fail closed.
6. When the object is absent: AE–AS bit-identity matches pre-plan for the same roster and seeds. A bare `Give` still creates no debt.
7. Optional read-only cognition context, ignored by the engine:
   - `ReputationMode=DETERMINISTIC` → fulfillment and violation may add reliability evidence through `note_remembered_reliability`. Absence → DEBUG `reputation_channel_off` and skip. Do not add `commitment_declared` to `_OBSERVATION_DELTAS`.
   - `SocialNormMode=DETERMINISTIC` and an existing `RECIPROCAL_EXCHANGE` belief → `note_reciprocal_commitment_evidence` may append one count. Absence, or no such belief, → skip. Never create the belief.
   - This ledger does not call `appraise_identity` and does not write `IdentityAspect.COMMITMENT`.
   - Relationship service is the V1 path. Emit only the four existing signals in the consequences table. `RESOURCE_RECEIVED` means the source owes the target. Do not add a dimension.

### Flag × object gate matrix (locked)

| Config shape | Allowed? | Reject / notes |
| --- | --- | --- |
| Object absent, schema v4–v38 | Yes (off) | Passthrough |
| Object present, schema ≠ v39 | No | `structured_commitments_requires_v39` |
| Schema v39 without the object | No | `v39_requires_structured_commitments` |
| Object present, any V3 flag off | Yes | Speech needs no flag |
| Object present, norms or reputation disabled | Yes | Consequence paths no-op |
| Object present, possession / cultural / lifecycle / genealogy / experimentation on v39 | Yes | Widen those schema allowlists through v39; add v39 to the local `_experiment_schemas` set; keep reject code `bounded_experimentation_requires_v36`; do not require those objects |
| Any forbidden enforcement alias | No | `structured_commitments_enforcement_forbidden` |
| `mode=disabled` present | No | `structured_commitments_mode_invalid` — omit the object for off |
| Unowned V3 flag true | No | existing `capability_unimplemented` |

### Runner schema (locked)

Introduce `RUNNER_SCHEMA_VERSION_V39 = "runner-config-v39"`:

- Exact root key set = **v38 accepted roots** ∪ sibling **`structured_commitments`**. `possession_succession` and the other v38 siblings stay optional.
- `structured_commitments` present ⇒ `schema_version == runner-config-v39`.
- Decode v23–v38 synthesizes `structured_commitments=None`.
- Gate rewrite: cultural, durable, historical-layer, repository, genealogy, experimentation, and possession allowlists that were extended to v38 in v3-16 also accept v39. Cultural-only still forbids `population_lifecycle`. It allows `structured_commitments` and `possession_succession`.
- Default write stays `runner-config-v4` when all V3 flags are off and this object is absent.
- **Write pair:** when the channel is active, `checkpoint_schema_for_production` returns `(EVENT_SCHEMA_REPLAY_V17, "v14")`, higher priority than `possession_succession_active` (v16/v13). Channel off does not select v17. Add keyword `structured_commitments_active: bool = False` and pass `config.structured_commitments is not None` from `src/simulation/runner.py`, `src/simulation/service.py`, and `src/simulation/engine.py`.
- **Loop kwargs:** `_structured_commitments_loop_kwargs` in `src/simulation/runner.py`, beside `_possession_succession_loop_kwargs`, passes `structured_commitments_active` and `max_open_interpretations` into `CognitiveLoop`. The world rule context carries `horizon_ticks` only.
- **Matrix finalize (Task 14 only):** in `src/experiments/matrix_schema.py`, insert `structured_commitments_on` immediately before `possession_succession_on`. Task 1 must **not** edit finalize priority.
- Alembic head stays `0017`. Protocol id stays `observer-protocol-v1`.

### Serialization contract (locked)

Mirror the v38 helper pattern in `runner_serialization.py`:

- v39 root keys = v38 family helper ∪ `{structured_commitments}` minus optional objects that are absent
- Exact child keyset `_STRUCTURED_COMMITMENTS_KEYS`
- `_encode_structured_commitments` / `_decode_structured_commitments` with `_require_keys`
- Encode: `schema_version == V39` requires the object
- Decode: v23–v38 → `None`
- DEBUG log `present`, `policy_id`, `horizon_ticks` on decode
- Reject forbidden enforcement aliases before key acceptance

### `StructuredCommitmentsSpec` (locked)

Root sibling object; omit for off. Exact keys (reject extras / missing):

| Key | Type / values | Role |
| --- | --- | --- |
| `policy_id` | `structured-commitments-v1` only | Closed policy id |
| `horizon_ticks` | int, `1..64` | Maximum `by_tick` distance from the declaration tick. Not a forget timer |
| `max_open_interpretations` | int, `1..16` | Per-owner cap. A new row past the cap is dropped. Oldest rows stay |

No default creditor, no damage table, no shared id seed.

### Runtime channel flags (locked)

1. `structured_commitments_active = config.structured_commitments is not None` at run start.
2. Pass a `StructuredCommitmentsRuleContext(allow_declare=True, horizon_ticks=...)` into `evaluate_operation` only when active. `WorldEngine.tick` passes it beside `possession_succession` context. `None` context ⇒ `DeclareCommitment` rejects with `STRUCTURED_COMMITMENTS_CHANNEL_OFF`. Other commands must not start returning that reason.
3. Subjective checkpoint field `structured_commitments` (owner id → ledger). Blank-slate key of the same name. Not a SQLAlchemy table.
4. **No objective agreement collection** on `WorldState`. Replay rebuilds nothing but ordinary events. Journal snapshots gain no agreement id list.

### Public declaration (locked)

New command `DeclareCommitment` (command count **37**):

| Field | Rule |
| --- | --- |
| `counterparty_id` | Living body, distinct from the actor, same location |
| `kind` | `promise` \| `future_exchange` \| `debt` \| `service_obligation` \| `conditional_agreement` |
| `act` | `propose` \| `accept` \| `report_fulfilled` \| `report_partial` \| `report_violated` \| `report_dispute` |
| `owed_by` | `self` \| `counterparty` |
| `item_kind` | `ItemKind` or omitted. The deferred or single material term. Wood is `material` |
| `service` | `none` \| `help` \| `feed` \| `transport` |
| `quantity` | `1` \| `2` \| `3` |
| `due_kind` | `none` \| `by_tick` \| `when_next_colocated` \| `if_counterpart_gives` |
| `due_tick` | Required iff `due_kind=by_tick`. Must lie in `[tick, tick + horizon_ticks]` |
| `now_item_kind` | Required iff `kind=future_exchange`. Otherwise omitted |

Term shape rejects:

- `future_exchange` without both `now_item_kind` and `item_kind`
- `service_obligation` unless `service != none` and `item_kind` is omitted
- `promise`, `debt`, and `conditional_agreement` unless exactly one of `item_kind` or `service != none` is set
- `act=accept` does not need a prior `propose` in the log
- Holding the named item is not required

Success emits `CommitmentDeclared` with those tokens plus `actor_id` and `tick`. Do not mutate items, health, relationships, or ledgers inside `WorldEngine`. A second declaration does not delete the first. There is no `CommitmentResolved` event and no world agreement id.

`Give`, `Help`, `Feed`, and `Transport` stay behaviorally unchanged. Cognition may later treat a witnessed occurrence as relevant to an owner's open row. The engine does not.

### Perception (locked)

`CommitmentDeclared` is a colocated public occurrence, not a private `Talk`.

`build_occurrence_context` and `_public_facts_for_role`:

- Actor and counterparty receive every token: kind, act, owed_by, item kind, service, quantity, due kind, due tick, now item kind.
- A colocated witness receives the same tokens. Divergence is not produced by hiding terms from people who were in the room.
- An agent in another location receives nothing for this event.
- `target_id_for_details` returns `counterparty_id`.

`Given` today exposes `kind`, `actor_id`, and `target_id` only (`_public_facts_for_role`). Item kind is not on the occurrence. When the channel is on, roles that already receive `actor_id` for a `Given` also receive `item_id` and `item_kind` looked up from world state. Channel off adds no keys, so existing give observations stay the same. `help`, `feed`, and `transport` already use those kind strings. Who sees a give does not grow. Bystanders who today receive only `kind` still receive only `kind`.

No ledger is copied onto the observation. Declared tokens are testimony about terms, even though delivery and the token list are world-verified. They are not a finding that the debt exists.

### Subjective ledger (locked)

Module `src/agents/cognition/structured_commitments.py`. Owner-scoped. Not on `Observation`.

Each interpretation row:

| Field | Meaning |
| --- | --- |
| `local_id` | Owner-local ordinal. Not shared. Not on the event |
| `source_event_ids` | Occurrences this owner folded in |
| `parties` | Speaker and counterparty as this owner stored them |
| `debtor_id`, `creditor_id` | Absolute ids resolved at first store from the speaker's `actor_id`, `counterparty_id`, and `owed_by`. Later revisions may change them. A dispute keeps the previous pair in `revisions` |
| `kind`, `owed_by`, `item_kind`, `service`, `quantity`, `now_item_kind` | This owner's terms. Unknown fields use `unspecified`, not a guess copied from a peer |
| `due_kind`, `due_tick`, `created_tick` | This owner's due condition |
| `status` | `proposed` \| `accepted` \| `open` \| `partial` \| `fulfilled` \| `violated` \| `disputed` \| `forgotten` |
| `now_matched` | Whether the immediate leg has been seen. Separate from the deferred count |
| `matched_quantity` | How many deferred items, or one service, this owner has counted. The now-leg `Give` does not increment this |
| `confidence` | Quantized unit interval, same style as relationship confidence |
| `memory_trace_ids` | This owner's traces. Empty is legal only before the link step; the updater must try to link |
| `revisions` | Append-only. A dispute appends. It does not overwrite the previous terms |

Updater inputs are that owner's observations of `CommitmentDeclared`, `Given`, `Helped`, `Fed`, and `Transported`, plus that owner's memory traces for the linked ids. No peer-ledger copy.

Binding rules, all local:

- `propose` opens a row with status `proposed`, or `open` when the speaker owes and the kind needs no second speaker (`promise` with `owed_by=self`). Resolve `debtor_id` / `creditor_id` immediately. `owed_by=self` → debtor is the speaker. `owed_by=counterparty` → debtor is the counterparty.
- `accept` opens or updates the row whose public tokens match this owner's stored terms. A mismatch appends a revision and sets `disputed`. It does not replace the older terms.
- A witnessed `Given` counts only when `public_facts` include `item_kind`, the actor is `debtor_id`, and the recipient is `creditor_id`. A third party's gift does not count. If `item_kind` equals `now_item_kind`, set `now_matched` and do not increment `matched_quantity`. If `item_kind` equals the deferred `item_kind`, increment `matched_quantity` by one, capped at `quantity`.
- Status becomes `partial` when `0 < matched_quantity < quantity`, and `fulfilled` when `matched_quantity >= quantity`. A quantity-1 future exchange stays open after the food `Give` and becomes fulfilled only after the material `Give`.
- A witnessed `help` / `feed` / `transport` occurrence fulfills a `service_obligation` of that service once, using `occurrence.kind`, and only when the actor is `debtor_id` and the target is `creditor_id`.
- Due rules, all beliefs, none of them damage or a rejected command:
  - `by_tick`: the due tick has passed and `matched_quantity < quantity` → `violated`.
  - `none`: never auto-violates.
  - `when_next_colocated`: stays `open` until the owner sees debtor and creditor together on a tick after `created_tick`. If that meeting ends with the later leg still short, set `violated`.
  - `if_counterpart_gives`: stays `proposed` until the owner sees the counterpart give `now_item_kind`, then becomes `open`. It does not violate for lack of that gift.
- `report_partial` and `report_fulfilled` do not increment `matched_quantity` or set `now_matched`. Matching tokens may confirm a status the counts already support. Differing tokens append a revision and set `disputed`.
- `report_violated` or `report_dispute` whose tokens differ from the stored row sets `disputed` and keeps both revisions.
- Past `max_open_interpretations` from the loop kwargs, drop the new row and DEBUG `commitment_dropped_over_cap`. Do not delete an older row. Do not call `appraise_identity`.

Blank slate: add `structured_commitments` to `BLANK_SLATE_SUBJECTIVE_STORES` in `src/simulation/new_agent_initialization.py`. A newborn does not receive a parent's debts.

### Forgetting (locked)

Forgetting is not a command and not `horizon_ticks`.

The link is `MemoryUpdateKind.WRITE_MEMORY` for the witnessed occurrence. After the runtime commits that intent, write the returned trace id onto that owner's row. A later tick reads `forgotten_at_tick` on those ids from the owner's already-loaded traces.

When every linked trace has `forgotten_at_tick` set, the current status becomes `forgotten` and the current term view becomes `unspecified`. The revision list keeps the last remembered terms. A peer who still holds traces stays `open` or `fulfilled`. Analysis counts that split. Do not call `forget` on another owner. Do not add a distortion code. If the trace link never succeeded, the row does not age out; DEBUG `commitment_unlinked`.

### Consequences (locked)

After a local status change, the updater may request, and only request:

`RESOURCE_RECEIVED` raises the source's `DEBT` toward the target (`src/social/relationships.py`). The source is always the ledger owner.

| Status change | Request |
| --- | --- |
| Owner is the debtor and status becomes `open` | `RESOURCE_RECEIVED`, target = creditor |
| Owner is the debtor and status becomes `fulfilled` | `RESOURCE_GIVEN`, target = creditor |
| Owner is the creditor and status becomes `fulfilled` | `CORROBORATION_RECEIVED`, target = debtor |
| Owner is the creditor and status becomes `violated` or `disputed` | `CONTRADICTION_RECEIVED`, target = debtor |
| Reputation on, fulfillment | `note_remembered_reliability` at `+0.10` |
| Reputation on, violation | `note_remembered_reliability` at `-0.10` |
| Norms on, and `RECIPROCAL_EXCHANGE` already exists for the pair | `note_reciprocal_commitment_evidence` appends one count |
| Violation | sanction token `criticism` or `shun` on the ledger |

`note_remembered_reliability` lives in `src/agents/cognition/reputation.py`. It appends one `REMEMBERED_INTERACTION` reliability item. Lineage is `commitment:{local_id}:{status}:{tick}`. If the existing evidence cap is full, DEBUG drop and do not raise. Do not add `commitment_declared` to `_OBSERVATION_DELTAS`. Do not call `apply_reputation_update` with a fake occurrence.

`note_reciprocal_commitment_evidence` lives in `src/agents/cognition/social_norms.py`. It returns the same ledger when no `RECIPROCAL_EXCHANGE` belief exists for that pair. It does not create a belief and does not call the private return-window recorder.

`retaliation_considered` is writable only by an explicit owner update API used in tests. The updater does not submit `Attack`, `Give`, or a second `DeclareCommitment`. Reputation and norm requests are skipped, not invented, when those modes are off. Relationship signals use the existing revision pipeline (`MemoryUpdateIntent` / relationship service). No signal may change health, inventory, or command legality. The creditor does not emit `RESOURCE_RECEIVED` for being owed.

### Analytical conventions (locked)

`src/analysis/structured_commitments.py`. Pure functions over detached events plus optional detached ledger snapshots. `WorldEngine` does not import this module.

Per public `CommitmentDeclared` with `act=propose` or `act=accept`:

| Field | Meaning |
| --- | --- |
| `speech` | The event tokens. This is what was said, not what is owed |
| `interpretations` | One row per owner ledger that cited the event. Missing ledger → that owner is absent, not "agreed" |
| `divergent` | True when two citing owners differ in kind, item kind, service, quantity, owed_by, or due kind |
| `fulfillment` | Histogram of those owners' statuses. No owner is the official status |
| `forgotten_split` | True when one citing owner is `forgotten` and another is not |
| `world_enforcement` | Always false. A non-false value is a test failure |
| `institution` | Always `none` |

A later `Given` is noted as `item_moved` with holder ids. It is not proof the matching interpretation was correct. Ties and mismatches stay `divergent`. No supports yield `unformed` for owners who never stored a row.

### Observer (locked)

Add exactly one semantic type, protocol id unchanged:

- `COMMITMENT_DECLARED`

The tuple length is 57 today. One addition makes **58**. Sweep every `len(SEMANTIC_EVENT_TYPES) == 57` pin.

Command count becomes **37** (`DeclareCommitment` only). `Give` is not duplicated.

### Experiment AT (locked)

Id `structured_commitments@1`. Off `OFF_GATE_MATRIX_EXPERIMENT_IDS` / V1 gate. Four arms, same seed and roster:

| Arm | Setup | Assertion |
| --- | --- | --- |
| `at-channel-off` | no object; scripted `Give` of food | item moves; no `CommitmentDeclared`; no ledger field; hash equals the pre-plan fixture |
| `at-food-now-material-later` | v39; tick N `Give` food and `DeclareCommitment` `future_exchange` (`now_item_kind=food`, `item_kind=material`, `quantity=1`, `due_kind=by_tick`); a later tick the counterparty `Give`s one material item | both events exist; each owner may be `fulfilled`; no command was rejected for lateness; the engine did not create the return `Give` |
| `at-divergent-terms` | v39; both owners hear one proposal and both store it; the arm then forgets only one owner's linked traces through that owner's memory service | that owner becomes `forgotten`; the other stays `open`; event tokens stay the original speech; no ledger poke and no shared row on `WorldState` |
| `at-no-collection` | v39; `due_tick` passes with no return `Give` | debtor health and inventory unchanged; creditor status may be `violated`; no `Attack`; `world_enforcement` is false |

Default batches do not enable AT. Scripted return `Give` and `DeclareCommitment` are explicit commands, not proposer side effects, so the arm does not depend on the proposer.

### Metric families (locked)

Three siblings. Pin `METRIC_FAMILY_COUNT` from 74 to **77**. Empty harvest when the channel is off.

| Family id | Reads | Does not |
| --- | --- | --- |
| `commitment_term_divergence` | speech events and per-owner terms | elect a true contract |
| `commitment_fulfillment_status` | status histogram, partial counts, forgotten splits | treat a status as a world fact |
| `commitment_social_consequences` | relationship, reputation, norm, and sanction request counts | count a health or inventory change as enforcement |

Research UI Analytics badges for these three ids only, overlay kind `research_inference`.

## Docs (mandatory checkpoint)

`/aif-implement` must route this through `/aif-docs` before done:

- `docs/social-communication.md` — structured commitments versus `Talk`, scalar debt, norm windows, and identity `COMMITMENT`
- `docs/cognition-runtime.md` — ledger, divergence, forgetting via traces, sanctions are not damage
- `docs/analysis-metrics.md` — three families, speech ≠ obligation
- `docs/architecture.md` — v39, replay-v17/codec v14 only when active, command 37, semantic count 58
- `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/ROADMAP.md` — M7 note; `institutional_economy` still unowned; no contract enforcement

Docs must not describe a declaration as a world rule.

## Commit Plan

- **Commit 1** (after tasks 1–3): `feat: add structured commitment config on runner-config-v39`
- **Commit 2** (after tasks 4–6): `feat: record public commitment speech without enforcing it`
- **Commit 3** (after tasks 7–11): `feat: keep diverging subjective debts and promises`
- **Commit 4** (after tasks 12–14): `feat: measure commitment divergence and social consequences`
- **Commit 5** (after task 15): `docs: describe promises and debts without contract enforcement`

## Tasks

### Phase 1: Schema

- [x] Task 1: Add `RUNNER_SCHEMA_VERSION_V39`, `StructuredCommitmentsSpec` (`policy_id`, `horizon_ticks`, `max_open_interpretations`), `SimulationRunnerConfig.structured_commitments`, exact encode/decode, forbidden-enforcement alias frozenset, and the reject codes in the flag×object matrix. Decode v23–v38 synthesizes `None`. Widen cultural, durable, historical-layer, repository, genealogy, experimentation, and possession schema allowlists through v39 without requiring those objects. Add v39 to the local `_experiment_schemas` set in `SimulationRunnerConfig` post-init and keep reject code `bounded_experimentation_requires_v36`. Cultural-only still forbids `population_lifecycle`. Do not edit matrix finalize priority (Task 14). Do not add a V3 flag.
  - Deliverable: Round-trip tests; rejects for v39 without the object, object on v38, `horizon_ticks` outside `1..64`, `mode=disabled`, and each forbidden enforcement alias; v38 possession config still loads; v39 with only `structured_commitments` loads with all V3 flags off.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `tests/unit/test_structured_commitments_spec.py`
  - Logging: DEBUG decode with `present`, `policy_id`, and `horizon_ticks` only; INFO/raise stable reject codes; never log term text at INFO
  - Depends on: none

- [x] Task 2: Add `EVENT_SCHEMA_REPLAY_V17` and codec `v14`. Add `structured_commitments_active: bool = False` to `checkpoint_schema_for_production` and select `(EVENT_SCHEMA_REPLAY_V17, "v14")` only when that flag is true, ahead of possession succession v16/v13. Pass `config.structured_commitments is not None` from `src/simulation/runner.py`, `src/simulation/service.py`, and `src/simulation/engine.py`. Channel off keeps the previous pair. Accept `CommitmentDeclared` only on v17. Replay-v16 decode rejects that kind. Add `_structured_commitments_loop_kwargs` beside `_possession_succession_loop_kwargs` and pass `structured_commitments_active` plus `max_open_interpretations` into `CognitiveLoop`.
  - Deliverable: Version-selection tests for channel off, possession on without this object, and this object on (with and without possession). Unknown kind on v16 fails closed. A v39 config reaches the loop with the spec cap. A v38 config leaves the new keyword false and the cap unset.
  - Files: `src/simulation/serialization.py`, `src/simulation/persistence.py`, `src/simulation/compatibility.py`, `src/simulation/runner.py`, `src/simulation/service.py`, `src/simulation/engine.py`, `src/agents/cognition/loop.py`, `src/agents/cognition/configuration.py`, `src/world/events.py`, `tests/unit/test_structured_commitments_replay_schema.py`
  - Logging: INFO `checkpoint_schema_selected` with replay version and codec; DEBUG channel flag and `max_open_interpretations` when active; ERROR on kind/schema mismatch with the kind name only
  - Depends on: 1

- [x] Task 3: Add event dataclass `CommitmentDeclared` with the command's public tokens plus `actor_id` and `counterparty_id`. Add it to the `EventDetails` union, `require_event_details`, `target_id_for_details`, and the replay `match` arms. Do not add an agreement collection to `WorldState` or to journal `WorldSnapshot`. Projection appends the event and changes no inventory or health.
  - Deliverable: Project a declaration and assert inventories, health, and `WorldState` fields match the pre-image. A v14 snapshot round-trips without a new agreement field. A folded v16 log has no declaration kind.
  - Files: `src/world/events.py`, `src/world/_replay.py`, `src/simulation/journal.py`, `tests/unit/test_commitment_declared_projection.py`
  - Logging: DEBUG `commitment_declared_projected` with kind, act, and `quantity`; no item lists at INFO
  - Depends on: 2

<!-- Commit checkpoint: tasks 1–3 -->

### Phase 2: Public speech

- [x] Task 4: Add command `DeclareCommitment` (command count 37) and rule evaluation under `StructuredCommitmentsRuleContext`. `WorldEngine.tick` passes that context, or `None` when the object is absent. Living colocated actor, living distinct counterparty, closed tokens, term-shape rules, and `by_tick` inside the horizon. Emit `CommitmentDeclared`. No item, health, relationship, or ledger mutation. Context `None` rejects with `STRUCTURED_COMMITMENTS_CHANNEL_OFF` only for this command. Wire the operation arm in `src/world/_operations.py` (missing arm is `MALFORMED_ENVELOPE`), command encode/decode in `src/simulation/serialization.py`, and causal-debugger kind maps in `src/simulation/causal_debugger.py`. Do not add `declare_commitment` to `LIFECYCLE_DENIED_COMMAND_KINDS_ALLOWLIST`. `Give` behavior stays unchanged, including a `Give` in the same tick.
  - Deliverable: Tests for a food-now / material-later declaration that does not move items; a same-tick `Give` still moves only the given item; channel-off declaration rejected; dead actor rejected; horizon miss rejected; service obligation with an item kind rejected; command registry includes the new command exactly once; a serialized command round-trips; a dependent stage can still select it. Passing a ledger into the rule context is a type error.
  - Files: `src/world/actions.py`, `src/world/structured_commitments.py`, `src/world/_rules.py`, `src/world/_operations.py`, `src/simulation/engine.py`, `src/simulation/serialization.py`, `src/simulation/causal_debugger.py`, `tests/unit/test_declare_commitment.py`
  - Logging: INFO `commitment_declared` with kind, act, and `owed_by`; DEBUG reject reason; never log a ledger
  - Depends on: 3

- [x] Task 5: Perception for `CommitmentDeclared`. Colocated actor, counterparty, and witnesses receive the full token set. Remote agents receive no occurrence. `target_id_for_details` returns the counterparty. Do not attach a ledger, a shared agreement id, or another agent's memory id. When the channel is on, roles that already receive `actor_id` for a `Given` also receive `item_id` and `item_kind` from world state. Channel off adds no keys to `Given`. Bystanders who today receive only `kind` still receive only `kind`. `help`, `feed`, and `transport` keep their existing kind strings.
  - Deliverable: Three colocated agents see the same declaration tokens; an agent in another location sees none; channel off emits no declaration occurrence; the observation has no ledger field. A channel-on colocated witness of `Given` sees `item_kind`; the same witness with the channel off does not. A remote agent still does not see the give.
  - Files: `src/world/observations.py`, `src/world/_perception.py`, `src/world/events.py`, `tests/unit/test_commitment_perception.py`
  - Logging: DEBUG `commitment_occurrence` with kind, act, and audience role; DEBUG `commitment_give_facts` with `item_kind` only when the channel adds it; no term text at INFO
  - Depends on: 4

- [x] Task 6: Observer semantic `COMMITMENT_DECLARED`. Protocol id unchanged. Map the kind in `SEMANTIC_TYPE_BY_KIND` and the causal-debugger semantic map. Godot stays read-only (no creditor overlay). Length is 57 today and 58 after. Sweep `len(SEMANTIC_EVENT_TYPES) == 57` in the observer, experiment-perception, and v3 regression tests that pin it.
  - Deliverable: Semantic tuple length is 58; a fixture declaration exports the new label; no remaining `== 57` pin.
  - Files: `src/observer/version.py`, `src/observer/contracts.py`, `src/simulation/causal_debugger.py`, and the pin files found by the sweep
  - Logging: DEBUG `observer_semantic_mapped` with kind and semantic; no payload bodies
  - Depends on: 4

<!-- Commit checkpoint: tasks 4–6 -->

### Phase 3: Subjective memory of agreements

- [x] Task 7: Add owner-scoped `structured_commitments` ledger types and the empty-ledger constructor. Export them from the cognition package. Add the store name to `BLANK_SLATE_SUBJECTIVE_STORES`. Checkpoint field round-trips only on codec v14; absent on older codecs. An older codec that still carries the key fails with `structured_commitments_requires_codec_v14`.
  - Deliverable: Blank-slate assert fails if a newborn ledger is non-empty; codec v13 checkpoint has no field; codec v14 round-trips two owners' different terms for one event id; cap constant is the spec value, not a world id.
  - Files: `src/agents/cognition/structured_commitments.py`, `src/agents/cognition/__init__.py`, `src/agents/cognition/models.py`, `src/agents/cognition/contracts.py`, `src/simulation/new_agent_initialization.py`, `src/simulation/run_control.py`, `src/simulation/serialization.py`, `tests/unit/test_structured_commitment_ledger.py`
  - Logging: DEBUG `commitment_ledger_updated` with owner id, local id, and status; INFO `blank_slate_asserted` includes the new store in the count; never log another owner's terms
  - Depends on: 2

- [x] Task 8: Cognition updater from the owner's own observations only, using the public facts from Task 5 and `max_open_interpretations` from the loop kwargs in Task 2. On first store, resolve absolute `debtor_id` and `creditor_id` from the speaker's `actor_id`, `counterparty_id`, and `owed_by`. Track `now_matched` separately from `matched_quantity`. A `Given` counts only when actor is the debtor, recipient is the creditor, and `item_kind` is present. The now-leg sets `now_matched` and does not increment `matched_quantity`. The deferred leg increments `matched_quantity`. `fulfilled` requires `matched_quantity >= quantity`. Apply the due rules for `by_tick`, `none`, `when_next_colocated`, and `if_counterpart_gives` from the ledger section. `report_partial` and `report_fulfilled` do not increment counts. Matching report tokens may confirm a status the counts already support. Differing tokens append a revision and set `disputed`. A service occurrence fulfills only when `occurrence.kind` matches and the actor/target are debtor/creditor. Do not read peer ledgers. Do not copy rows onto new agents. Do not call `appraise_identity`. Drop new rows past the cap without deleting older ones.
  - Deliverable: Tests for food-now leaving the row open and material-later making it `fulfilled`; a third-party `Given` of material leaving the count unchanged; quantity 2 then one deferred `Given` stays `partial`; `due_kind=none` does not violate after the horizon; `when_next_colocated` violates only after a meeting with the later leg still short; `if_counterpart_gives` stays `proposed` until that gift, then `open`; a `report_fulfilled` with a different item kind sets `disputed` and does not increment the count; a late `by_tick` with no return `Given` becomes `violated` without an `Attack` or a forced `Give`; blank child after a parent declaration; over-cap drop; no identity-aspect write.
  - Files: `src/agents/cognition/structured_commitments.py`, `src/agents/cognition/loop.py`, `src/simulation/agent_runtime.py`, `tests/unit/test_structured_commitment_update.py`
  - Logging: DEBUG `commitment_status` with local id and status; INFO only when status becomes `violated`, `disputed`, or `fulfilled`; no observation text
  - Depends on: 4, 5, 7

- [ ] Task 9: Link each adopted row by emitting `MemoryUpdateKind.WRITE_MEMORY` for the witnessed occurrence. After `agent_runtime` commits that intent, write the returned trace id onto that owner's row. On a later tick, read `forgotten_at_tick` from those traces. When every linked trace is forgotten, set status `forgotten` and the current term view to `unspecified`, keeping revisions. Do not forget a peer. Do not add a retention policy or distortion code. Unlinked rows do not age out.
  - Deliverable: Tests for one owner forgotten through that owner's memory service and the other still `open` after the same declaration; revision terms still readable after forgetting; unlinked row remains `open` past `horizon_ticks`; no cross-owner `forget` call.
  - Files: `src/agents/cognition/structured_commitments.py`, `src/agents/cognition/loop.py`, `src/simulation/agent_runtime.py`, `tests/unit/test_structured_commitment_forgetting.py`
  - Logging: DEBUG `commitment_memory_linked` with trace count; INFO `commitment_forgotten` with local id only; never log trace text
  - Depends on: 8

- [ ] Task 10: Consequence requests after local status changes, using the consequences table. The ledger owner is the relationship source. A debtor moving to `open` emits `RESOURCE_RECEIVED` toward the creditor. A debtor moving to `fulfilled` emits `RESOURCE_GIVEN` toward the creditor. A creditor moving to `fulfilled` emits `CORROBORATION_RECEIVED` toward the debtor. A creditor moving to `violated` or `disputed` emits `CONTRADICTION_RECEIVED` toward the debtor. Do not emit `RESOURCE_RECEIVED` from the creditor for being owed. Add `note_remembered_reliability` (`+0.10` / `-0.10`, lineage `commitment:{local_id}:{status}:{tick}`, drop on the existing evidence cap) and call it only when reputation mode is on. Add `note_reciprocal_commitment_evidence` and call it only when norm mode is on and a `RECIPROCAL_EXCHANGE` belief for the pair already exists. Do not add `commitment_declared` to `_OBSERVATION_DELTAS`. Do not add a relationship dimension. Store sanction tokens `none` \| `criticism` \| `shun` \| `retaliation_considered`. The updater never writes `retaliation_considered` and never submits `Attack`. Modes off skip with DEBUG. No request changes health, inventory, or admission.
  - Deliverable: Tests for a creditor violation emitting `CONTRADICTION_RECEIVED` and `criticism` only; a debtor `open` raising that owner's `DEBT` toward the creditor; a creditor `open` leaving `DEBT` unchanged; reputation delta absent when reputation is disabled; norm evidence absent when no reciprocal belief exists; evidence-cap drop does not raise; world tick after the request still admits a debtor `Give` of an unrelated item; no `Attack` in the proposal.
  - Files: `src/agents/cognition/structured_commitments.py`, `src/agents/cognition/loop.py`, `src/agents/cognition/reputation.py`, `src/agents/cognition/social_norms.py`, `tests/unit/test_structured_commitment_consequences.py`
  - Logging: DEBUG `commitment_consequence` with channel name (`relationship`, `reputation`, `norm`, `sanction`) and signal or token; INFO when a sanction other than `none` is stored; never log dimension floats at INFO
  - Depends on: 8

- [ ] Task 11: Deterministic proposer used only when the channel is on. After the owner's own successful `Give`, it may emit one `DeclareCommitment` `propose` of `future_exchange` whose `now_item_kind` is that item's kind and whose deferred `item_kind` is `material`, due `by_tick` at `tick + horizon_ticks`, quantity 1. If the observation contains a proposal naming the owner as counterparty, it may emit `accept` copying the perceived tokens, not a peer ledger. It must not emit the return `Give`, `Attack`, or a declaration when the channel is off. Channel off leaves the existing command ranking unchanged.
  - Deliverable: Tests for post-give proposal, accept-from-perception, no automatic return `Give`, channel-off ranking unchanged, and no `Attack`.
  - Files: `src/agents/cognition/structured_commitments.py`, `src/agents/cognition/deliberation.py`, `tests/unit/test_structured_commitment_proposer.py`
  - Logging: DEBUG `commitment_proposal` with command tag, kind, and act; INFO only when a proposal is selected; never log another owner's terms
  - Depends on: 5, 8

<!-- Commit checkpoint: tasks 7–11 -->

### Phase 4: Measurement

- [ ] Task 12: Implement `classify_commitment_speech` in `src/analysis/structured_commitments.py` from the analytical conventions table. Inputs are detached events plus optional ledger snapshots. Output separates speech tokens from per-owner interpretations. Missing ledgers yield `unformed` for that owner. `world_enforcement` is false. `institution` is `none`. A `Given` is `item_moved`, not a verdict.
  - Deliverable: Known-answer tests for speech-only, fulfilled after a matching give, partial quantity, divergent item kinds, forgotten split, channel-off empty list, and a fixture that fails if `world_enforcement` is true.
  - Files: `src/analysis/structured_commitments.py`, `src/analysis/__init__.py`, `tests/unit/test_structured_commitments_classify.py`, `tests/architecture/test_v3_structured_commitments_isolation.py`
  - Logging: DEBUG `commitment_speech` with `divergent`, `forgotten_split`, and status histogram counts; no agent rosters at INFO
  - Depends on: 6, 9, 10

- [ ] Task 13: Add the three metric families and pin `METRIC_FAMILY_COUNT` to 77. Sweep unit tests that assert `== 74`. Assemble only when the spec was present. Empty harvest when the object is absent. Research UI Analytics badges for the three family ids, kind `research_inference`, same pattern as possession-succession badges. No new graph panel.
  - Deliverable: Known-answer metric rows; channel-off empty; badge test; no remaining `METRIC_FAMILY_COUNT == 74` pin.
  - Files: `src/analysis/specifications.py`, `src/analysis/structured_commitments_metrics.py`, `src/analysis/metric_service.py`, `src/experiments/composition.py`, `src/experiments/collectors.py`, `clients/research-ui/src/epistemic.ts`, `clients/research-ui/src/views/AnalyticsPanel.svelte`, `clients/research-ui/src/epistemic.test.ts`, tests that pin the family count
  - Logging: DEBUG `structured_commitments_metrics_assembled` with family ids and row counts; UI badge titles must not call a status a legal fact
  - Depends on: 12

- [ ] Task 14: Register off-gate Experiment AT (`structured_commitments@1`) with the four arms in the design section. `at-divergent-terms` forgets one owner's linked traces through that owner's memory service after both have stored the same proposal. It does not write a different item kind into the ledger. Insert `structured_commitments_on` in `src/experiments/matrix_schema.py` immediately before `possession_succession_on`. Add the id to `OFF_GATE_MATRIX_EXPERIMENT_IDS`. Export the builder. AT stays off the V1 gate. `at-channel-off` hash matches the pre-plan fixture. The return `Give` in `at-food-now-material-later` is scripted, not left to the proposer. That arm stays `open` after the food `Give` and becomes `fulfilled` only after the scripted material `Give`.
  - Deliverable: Catalog tests for each arm; V1 regression gate and `test_v2_scientific_invariants` green with V3 flags off and without `structured_commitments`; `at-no-collection` proves debtor inventory and health are unchanged after the due tick; `at-divergent-terms` shows one `forgotten` owner and one `open` owner against the same speech event.
  - Files: `src/experiments/catalog.py`, `src/experiments/__init__.py`, `src/experiments/matrix_schema.py`, `tests/unit/test_experiment_at.py`
  - Logging: INFO `experiment_arm_start` with arm id and schema version; DEBUG `structured_commitments_active`
  - Depends on: 4, 10, 13

<!-- Commit checkpoint: tasks 12–14 -->

### Phase 5: Docs

- [ ] Task 15: Docs checkpoint listed in the Docs section. Confirm Alembic head `0017`, protocol id unchanged, command count 37, semantic count 58, write pair v17/v14 only when the channel is on, and no enforcement helper in `src/world`. Run `ruff check` on the changed Python set before this commit.
  - Deliverable: Doc updates; architecture isolation green; ruff clean on the changed set.
  - Files: `docs/architecture.md`, `docs/social-communication.md`, `docs/cognition-runtime.md`, `docs/analysis-metrics.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/ROADMAP.md`
  - Logging: none in docs; docs must say a declaration is speech and a ledger status is a belief
  - Depends on: 14

<!-- Commit checkpoint: task 15 -->
