# Phase 1: Contract and Owner-Scoped Market Cognition

Plan: [index.md](index.md)
Tasks: 1-4
Depends on: none

## Objective

Own the already-declared `markets_credit` V4 context, add one owner-scoped
market institution ledger, and add bounded `mkt_v1` speech frames plus a local
attendance planner. No world command, event, observer semantic type, replay or
codec marker, write pair, runner schema, SQL migration, price, money, credit,
debt, score, or ranking is added.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/simulation/v4_architecture.py` | `V4ContextId.MARKETS_CREDIT` (70), `V4_CONTEXTS` entry (212-228) | Declared authority `OWNER_SCOPED`, owners `agents.cognition`/`simulation`, prerequisites `SUPPLY_CHAINS`/`ORGANIZATIONS`, non-goals "no money object, price index, or ledger authority" and "no central bank or enforced debt" |
| `src/simulation/runner_models.py` | `_V4_OWNED_CAPABILITY_FLAGS` (327-337), `V4CapabilityFlags.markets_credit` (1147), `unimplemented_enabled_names` (1165-1177) | Ownership gate that must accept `markets_credit` |
| `src/simulation/compatibility.py` | `V4_OWNED_CAPABILITY_FLAGS` (155-165), V4 prose (780-793) | Duplicate owned-flag pin consumed by architecture tests |
| `src/simulation/runner.py` | `_cognition_config_for` (1024-1035), org mode/ policy mapping (1438-1451), call sites (2870, 6661, 7052) | Flag-to-cognition seam; the V4 flag is global and is not a runner key |
| `src/agents/cognition/configuration.py` | `CognitionOrganizationMode` (454-463), `CognitionMigrationDisplacementMode` (353-363), config fields (687, 736-741), fingerprint (1652, 1758-1773), factory (2081-2084) | Internal per-agent mode pattern derived from a V4 flag |
| `src/agents/cognition/organization_operations.py` | policy (257-312), records (733-1330), `OrganizationOperationLedger` (1427), update (2708), owner/cap guards (1536, 2739-2760) | Ledger structure, caps, owner scope, deterministic trimming |
| `src/agents/cognition/organization_operations_communication.py` | subject/predicates (63-88), claim encode/decode (161-303), utterance decorator (486-537) | Bounded speech-frame grammar and attachment pattern |
| `src/agents/cognition/contracts.py` | `Perspective` field (175), `require_owner_*` (420-427), `to_snapshot` (634) | Owner-safe carry boundary |
| `src/agents/cognition/models.py` | `SubjectiveSnapshot` (743, 1082-1090), `CognitiveLoopProposal` (3996), `CognitiveLoopResult` (4358) | Snapshot/proposal/result plumbing |
| `src/agents/cognition/loop.py` | prepare (5159, 5396-5405), `_prepare_organization_operations` (2625-2672), proposal carry (5834), complete (5943, 6289) | Where a ledger is prepared and committed |
| `src/agents/cognition/fork_state.py` | `prepared_organization_operations` (61), export/restore (1653, 1710) | Fork-state parity |
| `src/simulation/agent_runtime.py` | slots (472-479, 638), commit (1322-1340, 3034), restore (3624-3635), export (3805) | Runtime carry and checkpoint |
| `src/simulation/run_control.py` | `AgentRuntimeCheckpoint.organization_operations` (615), validation (780-788) | Durable checkpoint contract |
| `src/simulation/runner.py` | restore validation (5003-5043), organization ledger export (5681-5692), result assembly (5297-5298), migration ledger export (5800) | Runner checkpoint and result export |
| `src/simulation/runner_models.py` | `SimulationResult.migration_displacement_ledgers` (6404), ordered validation (6838-6867) | Result ledger field pattern |
| `src/agents/cognition/deliberation.py` | conflict `Wait` replacement (1196-1219), org frame attachment (1364-1375), `Move` compilation (2727-2737) | Hook ordering and existing-command compilation |
| `src/world/actions.py` | `Move` (53-59), `NegotiateExchange` (883-908), `AgentCommand` (911-955) | Only existing commands may be produced |
| `src/world/observations.py` | `ObservedOccurrence` (1029-1072), `VisibleExit` (285-300) | Exchange evidence and adjacent destination |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/agents/cognition/market_institutions.py` | create | Contract, enums, policy, ids, value objects, ledger, update, owner/cap guards |
| `src/agents/cognition/market_institutions_communication.py` | create | `mkt_v1` frame grammar, parsing, relation encoding, utterance attachment |
| `src/agents/cognition/market_institutions_actions.py` | create | One-step local attendance that may return an existing `Move` |
| `src/agents/cognition/configuration.py` | modify | `CognitionMarketMode`, policy field, validation, fingerprint, factory forwarding |
| `src/agents/cognition/contracts.py` | modify | `Perspective.market_institutions` field and owner validation |
| `src/agents/cognition/models.py` | modify | Snapshot/proposal/result fields |
| `src/agents/cognition/loop.py` | modify | Prepare, propose, complete, fork-state hooks |
| `src/agents/cognition/fork_state.py` | modify | Prepared ledger carry |
| `src/agents/cognition/deliberation.py` | modify | Attendance hook and `mkt_v1` attachment |
| `src/simulation/agent_runtime.py` | modify | Slot, commit, restore, checkpoint export |
| `src/simulation/perception.py` | modify | Owner-safe perspective projection parameter and pass-through |
| `src/simulation/run_control.py` | modify | Checkpoint field and validation |
| `src/simulation/runner.py` | modify | `markets_enabled` seam, restore/export, result ledger export |
| `src/simulation/runner_models.py` | modify | `market_institution_ledgers` result field and ordered validation |
| `src/simulation/compatibility.py` | modify | Add `markets_credit` to the owned pin and update prose |
| `src/agents/cognition/__init__.py` | modify | Public facade exports |

## Task 1: Lock `market-institutions.v1` contract, policy, and identifiers

### Intent

Give every later task one closed vocabulary and one deterministic identity and
cap policy, so the ledger, analysis, snapshot, and metric layers cannot drift.
This is an owner-scoped cognition contract; it adds no world type.

### Implementation Steps

1. Create `src/agents/cognition/market_institutions.py` with
   `MARKET_INSTITUTIONS_POLICY_VERSION = "market-institutions.v1"`,
   `MARKET_BELIEF_PREFIX = "mktb-"`, `MARKET_BELIEF_HEX_LEN = 16`,
   `MARKET_LABEL_MAX_LEN = 32`, `MARKET_LABEL_PATTERN =
   r"^[a-z0-9][a-z0-9_-]*$"`, and `MARKET_ANCHOR_MAX_LEN = 64`.
2. Declare closed enums exactly once:
   - `MarketExpectation`: `none`, `weak`, `expected`, `strong`.
   - `MarketCadence`: `single_occurrence`, `recurring_interval`,
     `periodic_window`, `unknown`.
   - `MarketVenueStatus`: `emerging`, `expected`, `persistent`, `declining`,
     `dormant`.
   - `MarketRoleKind`: `broker`, `host`, `organizer`, `unknown`.
   - `MarketRoleBasis`: `observed_participation`, `claimed`, `office`,
     `organization`.
   - `MarketRecordKind`: `exchange_record`, `attendance_record`,
     `agreement_record`, `unknown`.
   - `MarketScheduleSource`: `observed`, `communicated`, `self_authored`.
3. Declare `MARKET_FORBIDDEN_FIELD_NAMES` = `price`, `rate`, `money`,
   `currency`, `numeraire`, `clearing_price`, `bid`, `ask`, `spread`, `fee`,
   `commission`, `tax`, `debt`, `credit_limit`, `market_score`, `ranking`,
   `severity`, `recommendation`, `allocation`, `quota`, `central_planner`.
   Add `_reject_forbidden_fields(dataclass_type)` and call it from every
   dataclass `__post_init__`.
4. Declare `MarketInstitutionPolicy` (frozen, slots) with locked defaults:
   `max_venues=8`, `max_observations_per_venue=64`,
   `max_schedules_per_venue=4`, `max_roles_per_venue=8`,
   `max_records_per_venue=8`, `max_counterparties_per_observation=16`,
   `max_notices=8`, `max_evidence_per_observation=8`, `decline_after_ticks=64`,
   `dormant_after_ticks=128`, `expected_min_observations=2`,
   `strong_min_observations=2`, `strong_min_confidence_milli=500`,
   `persistent_min_ticks=3`, `persistent_min_windows=2`.
   Expose `MARKET_INSTITUTION_LOCKED_POLICY: Mapping[str, object]` and
   `default_market_institution_policy()`.
5. Add `market_venue_belief_id(*, owner_id: AgentId, location_id: EntityId,
   creation_tick: int) -> str`: SHA-256 over
   `f"{owner_id.value}\x1fmktb\x1f{location_id.value}\x1f{creation_tick}"`,
   first 16 lower-case hex, prefixed `mktb-`. Validate with
   `require_market_belief_id`.
6. Add `market_schedule_is_active(schedule, tick) -> bool` implementing:
   `recurring_interval` → `interval_ticks` and `phase_tick` set and
   `(tick - phase_tick) % interval_ticks == 0`; `periodic_window` →
   `window_index` set and `tick // 32 == window_index`; `single_occurrence` and
   `unknown` → `False`.
7. Add `MarketInstitutionError(ValueError)` with a `reason_code` property
   returning `args[0]`. Error codes are stable strings prefixed
   `market_institution_`.

### Required Interfaces and Contracts

- `MarketScheduleBelief` invariants: `recurring_interval` requires
  `interval_ticks` in `1..512` and `phase_tick` in `0..511`, and rejects
  `window_index`; `periodic_window` requires `window_index` in `0..511` and
  rejects interval/phase; `single_occurrence` and `unknown` reject all three.
  `confidence_milli` in `0..1000`.
- `MarketRoleClaim` invariants: `recognized` is true only when `basis` is
  `office` or `organization` and the matching ref is non-null; both refs are
  null for `observed_participation` and `claimed`.
- `MarketRecordRef.anchor` matches
  `^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$`; no payload text is accepted.
- `MarketVenueObservation.counterparty_ids` are sorted unique `EntityId` values;
  `exchange_count >= 0`; `exchange_count > 0` requires a non-empty counterparty
  tuple.

### Requirement Evidence

- Original Request: "Do NOT create a global Market class with authoritative
  prices"; "market schedules as social conventions".
- `src/simulation/v4_architecture.py:212-228` — owner-scoped authority and the
  no-money/no-price/no-ledger-authority non-goals.
- `.ai-factory/ARCHITECTURE.md` "Key Principles" 1-5 (separate authorities,
  deterministic identity, frozen contracts, off-path neutrality, safe logs).

### Error Handling and Logging

- Hooks log metadata only: `market_institution_contract_invalid
  reason_code=<code>` at ERROR from `MarketInstitutionError` construction paths.
- Never log labels, counterparties, location tokens, record anchors, utterance
  bodies, or valuations.
- No wall-clock, `hash()`, UUID, or global RNG is used for identity or time.

### Tests

- `tests/unit/test_market_institutions_contract.py`:
  - policy version and locked policy values are exact;
  - every enum has exactly its documented members in order;
  - belief ids are stable, owner-local, and differ across owners;
  - schedule invariants and active-tick boundaries (`phase`, modulo, window);
  - forbidden fields are rejected on a deliberately bad contract dataclass;
  - no `AgentCommand`/`WorldEvent` subclass exists in the module.
- `tests/unit/test_market_institutions_activation.py` (minimum surface): import
  the facade and assert it exposes only the documented names.

### Acceptance Criteria

- One module defines the contract, policy, ids, and error codes; no other module
  re-declares a threshold or enum value.
- `market_venue_belief_id` is deterministic across processes and never includes
  a wall-clock value.

### Verification

- `uv run pytest tests/unit/test_market_institutions_contract.py -q`
- Expected result: all pass.

## Task 2: Add the owner-scoped market institution ledger

### Intent

Turn repeated own-observed exchange at the current location into bounded,
owner-scoped venue beliefs with expectations, schedules, role claims, and record
anchors. The ledger stores no price, valuation, inventory, or peer state.

### Implementation Steps

1. Define frozen value objects:
   `MarketVenueObservation(tick, source_tick, counterparty_ids, exchange_count,
   proposal_count, withdrawn_count, digest)`,
   `MarketMeetingExpectation(level, evidence_count, first_tick, last_tick)`,
   `MarketScheduleBelief(cadence, interval_ticks, phase_tick, window_index,
   confidence_milli, source, first_tick, last_tick)`,
   `MarketRoleClaim(role_kind, basis, actor_id, office_ref, organization_ref,
   recognized, first_tick, last_tick)`,
   `MarketRecordRef(record_kind, anchor, first_tick, last_tick)`,
   `MarketVenueBelief(venue_id, owner_id, location_id, label_token, status,
   first_tick, last_tick, observations, expectation, schedules, roles, records,
   notices)`,
   `MarketInstitutionLedger(owner_id, venues, notices, policy_version)`.
2. Add `empty_market_institutions(owner_id)` and
   `require_owner_market_institutions(ledger, owner_id, *,
   field_name="ledger")`.
3. Add `apply_market_institution_update(*, owner_id, tick, observation, prior,
   offices=None, organization_concepts=None, policy=None) ->
   MarketInstitutionLedger`:
   - reject foreign `prior`, `offices`, and `organization_concepts`;
   - collect own-participation occurrences: `kind == "exchange_completed"`,
     owner `actor_id` or `other_entity_id`, and
     `0 <= observation.tick - provenance.source_tick <= 1`; location is
     `observation.location_id`;
   - collect `exchange_proposed` as `proposal_count` and
     `exchange_withdrawn` as `withdrawn_count` from the same owner audience
     under the same tick-gap rule;
   - if `observation.tick - source_tick > 1`, add notice `market_venue_stale`
     and skip the occurrence or attempt without incrementing any count; if
     `source_tick > observation.tick`, reject the occurrence as
     `market_institution_invalid_evidence`;
   - aggregate observations per `(location_id, source_tick)` and bind them to
     the owner-local venue whose `location_id` matches, minting a belief only
     when at least one own-participation exchange was observed; a repeated fold
     for the same `(venue_id, source_tick)` replaces the existing observation
     and never adds a second count;
   - compute `digest` as the first 16 lower-case hex characters of
     `sha256("market-observation\x1f" + venue_id + "\x1f" + str(source_tick) +
     "\x1f" + ",".join(sorted(counterparty_id.value)) + "\x1f" +
     str(exchange_count) + "\x1f" + str(proposal_count) + "\x1f" +
     str(withdrawn_count))`; the digest is an identity aid and is never logged;
   - update `first_tick`/`last_tick`, expectation (`none` at zero, `weak` below
     `expected_min_observations`, `expected` at `expected_min_observations` or
     more, `strong` at `strong_min_observations` or more with a schedule of
     confidence `>= strong_min_confidence_milli`), and status (`emerging` while
     observations are below `expected_min_observations`, `expected` at or above
     it, `persistent` when `persistent_min_ticks`
     distinct ticks span `persistent_min_windows` or more 32-tick windows,
     `declining` after `decline_after_ticks`, `dormant` after
     `dormant_after_ticks`);
   - default `label_token` is `venue-<first 8 hex of venue_id>`;
   - set `notices` from a closed set only.
4. Add deterministic trimming: venues sorted by `(last_tick, venue_id)` keeping
   the newest `max_venues`; observations/schedules/roles/records sorted by their
   documented keys and trimmed to their caps; notices sorted unique and capped.
   Any trim adds `market_ledger_truncated`.
5. Add `validate_market_institution_caps(ledger)` returning `None` or raising
   `market_institution_cap_exceeded`.
6. Export the contract through `src/agents/cognition/__init__.py` in the public
   facade (`__all__` includes only documented names).

### Required Interfaces and Contracts

- A ledger never stores another owner's `AgentId`, observation, or memory; every
  `EntityId` counterparty is a token visible to the owner.
- `MarketVenueBelief.location_id` is an objective `EntityId` copied from the
  observation, never a name.
- Role refs are opaque: `office_ref` is a 16-hex role signature, and
  `organization_ref` matches `^orgc-[0-9a-f]{16}$`. Unresolved refs produce
  `recognized=False` and notice `market_role_unresolved`.
- No field may hold `ItemKind`, item ids, valuations, prices, inventories, or
  arbitrary utterance text.
- Observation identity is `(venue_id, source_tick)`; folding the same source
  tick twice replaces the row and never increments counts. A prior-event gap of
  one tick is accepted; a larger gap is stale and skipped.

### Requirement Evidence

- Original Request: "agents repeatedly trade at location → expectations form →
  records/roles emerge"; "brokers if emergent"; "exchange records".
- `src/agents/cognition/organization_operations.py:1334-1510` — one owner-local
  sidecar per concept, caps, notices, tick ordering.
- `src/agents/cognition/loop.py:2196-2264` — own-observed
  `exchange_completed` fold that reads only occurrence facts.

### Error Handling and Logging

- Reject foreign owner/prior with `market_institution_foreign_ledger` and log
  `market_institution_update_rejected reason_code=foreign_ledger` at WARN.
- Reject malformed refs/anchors with `market_institution_invalid_role_ref` /
  `market_institution_invalid_anchor`.
- DEBUG: `market_institution_update owner_len=1 venues=<n>
  observations=<n> notices=<n>` (counts only).
- Never log venue labels, location ids, counterparties, role refs, anchors.

### Tests

- `tests/unit/test_market_institutions_ledger.py`: empty ledger owner scope;
  foreign prior rejection; own vs peer exchange filtering; a source tick one
  before the observation tick is counted; a gap of two ticks sets
  `market_venue_stale`; folding the same `(venue_id, source_tick)` twice leaves
  counts, digest, and ledger bytes unchanged; expectation transitions; status
  transitions at 64/128 ticks; schedule confidence; role recognition matrix;
  record anchor validation; caps and truncation; no forbidden fields; no
  command/event class.
- `tests/unit/test_market_institutions_isolation.py`: two owners observing the
  same exchange never share a ledger or venue id; exported rows contain only the
  owner's own venue set.

### Acceptance Criteria

- Two sell/buy sides of one exchange each fold their own belief; neither ledger
  contains the other owner's view.
- A ledger with eight venues and 64 observations per venue validates; adding one
  more venue trims deterministically and sets `market_ledger_truncated`.

### Verification

- `uv run pytest tests/unit/test_market_institutions_ledger.py tests/unit/test_market_institutions_isolation.py -q`
- Expected result: all pass.

## Task 3: Own the `markets_credit` flag and thread activation

### Intent

Make `markets_credit` an owned V4 flag on the accepted `runner-config-v56`
seam, and activate the ledger per agent from that global flag. No new runner
schema, root field, per-agent runner key, or capability slot is introduced.

### Implementation Steps

1. Add `"markets_credit"` to `_V4_OWNED_CAPABILITY_FLAGS` in
   `src/simulation/runner_models.py:327-337` and to
   `V4_OWNED_CAPABILITY_FLAGS` in `src/simulation/compatibility.py:155-165`.
   Update the V4 prose in `compatibility.py:780-793` to name V4-20 and state
   that four flags remain unowned.
2. Add `CognitionMarketMode(StrEnum)` with `DISABLED`/`DETERMINISTIC` to
   `src/agents/cognition/configuration.py`, plus
   `market_institution_mode: CognitionMarketMode = DISABLED` and
   `market_institution_policy: MarketInstitutionPolicy | None = None` on
   `CognitionLoopConfig`. Validate exact types, add
   `market_institution_mode` and `market_institution_policy_version` to the
   deterministic fingerprint only when enabled, and forward both through
   `build_cognitive_loop`.
3. Extend `_cognition_config_for(..., markets_enabled: bool = False)` in
   `src/simulation/runner.py`; map the flag to `DETERMINISTIC` plus
   `default_market_institution_policy()` or to `DISABLED` plus `None`. Pass
   `markets_enabled=(config.v4_capability_flags.markets_credit)` at the three
   call sites (2870, 6661, 7052).
4. Add the ledger to the cognition lifecycle:
   - `CognitiveLoop.__init__`: normalized mode, policy, and
     `_prepared_market_institutions = None`;
   - `CognitiveLoop.prepare`: call `_prepare_market_institutions` after
     `_prepare_organization_operations`; fold prior snapshot only when the exact
     ledger type and owner match; call `apply_market_institution_update` with the
     prepared organizations concepts and offices;
   - `CognitiveLoopProposal.market_institutions` and
     `CognitiveLoopResult.market_institutions`; `CognitiveLoop.complete` applies
     the proposal to runtime state;
   - `fork_state` carries and restores the prepared ledger.
5. Carry the ledger through owner-safe boundaries:
   - `Perspective.market_institutions` with
     `require_owner_market_institutions` in `contracts.py`;
   - `SubjectiveSnapshot.market_institutions` with validation in `models.py`;
   - `src/simulation/perception.py` projection parameter and pass-through for the
     new snapshot field;
   - `AgentRuntimeCheckpoint.market_institutions` in `run_control.py` with
     validation;
   - `AgentRuntime` slot, `_commit_market_institutions`, checkpoint restore and
     export;
   - runner checkpoint restore/export;
   - `SimulationResult.market_institution_ledgers: tuple[object, ...] = ()`
     with the same ordered, unique-owner, exact-type validation as
     `migration_displacement_ledgers` (`runner_models.py:6404,6838-6867`);
   - `SimulationRunner.export_market_institution_ledgers()` returning
     owner-ordered ledgers and assigning the result field at result assembly.
6. Keep `runner-config-v56` the only V4 schema; do not add `runner-config-v57`,
   a root field, or a per-agent `AgentCognitionSpec` key.

### Required Interfaces and Contracts

- Flag-off path allocates no policy, no ledger, no snapshot field, and produces
  no logs above DEBUG.
- A disabled loop returns `None` from `_prepare_market_institutions`; a
  checkpoint with a ledger but a disabled mode clears the field and logs
  `market_institution_checkpoint_cleared` at WARN.
- Foreign or wrong-type ledger at any carry boundary raises `TypeError` or
  `ValueError` with a stable message; it is never silently dropped.
- `markets_credit=True` with `runner-config-v56` constructs; enabling it does
  not activate any write pair.

### Requirement Evidence

- `src/simulation/v4_architecture.py:212-228` — `markets_credit` is declared
  owner-scoped and event-reusing.
- `src/simulation/runner.py:1438-1451` — the `organizations` flag-to-mode
  pattern this task mirrors.
- `.ai-factory/ARCHITECTURE.md` "Versioned Extension Contract" — accepted-set
  discipline and no silent schema widening.

### Error Handling and Logging

- INFO: `market_institution_ledger_exported owners=<n>`.
- WARN: `market_institution_checkpoint_cleared
  reason_code=channel_disabled`.
- ERROR: `market_institution_carry_rejected reason_code=foreign_ledger`.
- Never log owner ids, venue counts per owner, or ledger contents.

### Tests

- `tests/unit/test_market_institutions_config.py`: disabled mode allocates no
  policy; deterministic installs the locked policy; invalid mode/policy fails
  closed; fingerprint changes only when enabled; factory forwards.
- `tests/unit/test_market_institutions_runtime.py`: disabled loop has no
  ledger; enabled loop prepares one; perspective → snapshot → checkpoint
  round-trips; fork state carries the prepared ledger; runtime rejects foreign
  ledgers.
- `tests/unit/test_market_institutions_activation.py`: `markets_credit=True`
  constructs a runner on v56 and exposes an owned flag; `v4_scaffolding_profile`
  still rejects the enabled flag; no `runner-config-v57` string in `src/`;
  result carries owner-ordered ledgers and an all-off run carries `()`.

### Acceptance Criteria

- `V4CapabilityFlags(markets_credit=True).owned_enabled_names() ==
  ("markets_credit",)` and `unimplemented_enabled_names() == ()`.
- Flag-off checkpoints are byte-identical to the pre-change baseline.
- No new runner schema constant appears in `src/` or `tests/`.

### Verification

- `uv run pytest tests/unit/test_market_institutions_config.py tests/unit/test_market_institutions_runtime.py tests/unit/test_market_institutions_activation.py -q`
- Expected result: all pass.

## Task 4: Add `mkt_v1` speech frames and local attendance planning

### Intent

Let owners announce and expect meetings, claim broker-like roles, and cite
records through existing speech, and let an otherwise idle owner walk to an
expected adjacent venue. Both paths use existing commands and owner beliefs
only.

### Implementation Steps

1. Create `src/agents/cognition/market_institutions_communication.py` with
   `MARKET_FRAME_SUBJECT = "mkt_v1"`, `MARKET_COMMUNICATION_POLICY_VERSION =
   "market-institutions-communication.v1"`, `MARKET_FRAME_MAX_CHARS = 256`, and
   `MARKET_FRAME_MAX_RELATIONS = 32`.
2. Declare predicates `mkt_meeting`, `mkt_expect`, `mkt_decline`, `mkt_role`,
   `mkt_record` mapped from acts `announce_meeting`, `expect_meeting`,
   `decline_meeting`, `claim_role`, `cite_record` (bijective).
3. Encode exactly ten colon-separated fields:
   `mkt_v1:<predicate>:<label>:<expectation>:<cadence>:<interval>:<phase>:<role_kind>:<role_ref>:<anchor>`.
   Use `none` for null slots. Decode fail-closed on wrong part count, unknown
   subject/predicate/enums, bad label/ref/anchor, or control characters.
4. Add `market_claim_relation(claim)` and
   `parse_market_claim_relation(relation)` returning `None` for unrelated
   subjects/predicates; malformed `mkt_v1` objects raise
   `MarketInstitutionError`.
5. Add `market_communicate_utterance(command, ledger)`: applies only to exact
   `Talk`/`Tell`, only with an enabled non-empty ledger, never duplicates an
   existing `mkt_v1` relation, respects the relation cap, and preserves command
   class, recipient, utterance, and all existing relations.
6. Fold inbound frames in `apply_market_institution_update` from
   `observation.communications` where the owner is speaker or listener. Resolve
   labels only against the owner's own venues; an unknown label adds notice
   `market_venue_unresolved` and changes nothing. Speaker-authored frames are
   `self_authored`; peer frames are `communicated`. A peer cannot claim a role
   for a third actor: the claim is retained as `claimed` with
   `recognized=False`.
7. Create `src/agents/cognition/market_institutions_actions.py` with
   `market_attendance_command(command, *, owner_id, tick, observation, ledger,
   policy) -> AgentCommand`:
   - return the same object when `type(command) is not Wait`, the ledger is not
     an exact `MarketInstitutionLedger`, the owner differs, or no candidate
     exists;
   - candidates are venue beliefs with status `expected` or `persistent`, an
     active schedule for `tick`, and `location_id` different from
     `observation.location_id`;
   - sort candidates by `venue_id`; for the first candidate whose
     `location_id` equals an `observation.exits[*].destination_id`, return
     `Move(destination_id=destination)`;
   - otherwise return the same command object.
8. Invoke the hook in `src/agents/cognition/deliberation.py` after
   `organized_conflict_wait_replacement` and before speech-frame attachment.
   Invoke `market_communicate_utterance` after
   `organization_operation_communicate_utterance`.
9. Export the public helpers through `src/agents/cognition/__init__.py`.

### Required Interfaces and Contracts

- The attendance helper returns one existing `world.actions.Move` or the input
  command; it never constructs another command class, never pathfinds, never
  multi-hops, and never mutates the ledger or observation.
- Frames carry no item ids, prices, valuations, inventories, or free text.
- A frame longer than 256 characters or with more than 32 relations is dropped
  with a bounded WARN count; it is never truncated silently.
- No `mkt_v1` frame is attached to a command that is not `Talk`/`Tell`.

### Requirement Evidence

- Original Request: "meeting expectations"; "brokers if emergent"; "market
  schedules as social conventions".
- `src/agents/cognition/organization_operations_communication.py:207-303,486-537`
  — encode/decode/decorate pattern.
- `src/agents/cognition/deliberation.py:1196-1219,2727-2737` — existing-command
  replacement and exit-checked `Move`.

### Error Handling and Logging

- WARN: `market_frame_dropped reason_code=oversize` /
  `relation_cap` / `speaker_mismatch` with counts only.
- DEBUG: `market_attendance_selected candidates=<n>`; never log the destination
  or venue id.
- ERROR: `market_frame_invalid reason_code=<code>`.
- No utterance body or role/anchor token is logged.

### Tests

- `tests/unit/test_market_institutions_communication.py`: every act/stance
  round-trips; wrong part count/enum/ref/anchor fails; unrelated relations
  return `None`; decorator preserves class/recipient/relations; no-op on
  `Wait`/disabled; no duplicate `mkt_v1`; relation cap.
- `tests/unit/test_market_institutions_actions.py`: only `Wait` is replaceable;
  no exit → unchanged identity; exit → `Move`; status/schedule gating; owner
  mismatch unchanged; helper does not mutate the ledger; `Move` destination is
  an observed exit.
- `tests/unit/test_market_institutions_update.py`: inbound frames adopt
  schedule/expectation/role/record claims; unknown label notice; peer role
  claim stays `claimed`; speaker-only evidence.

### Acceptance Criteria

- An owner with an expected venue at an adjacent location replaces `Wait` with
  one `Move` to that exit; an owner without an exit keeps the identical `Wait`.
- A `Tell` can carry both an existing `org_v1`/`org_op_v1` relation and one
  `mkt_v1` relation without losing either.

### Verification

- `uv run pytest tests/unit/test_market_institutions_communication.py tests/unit/test_market_institutions_actions.py tests/unit/test_market_institutions_update.py -q`
- Expected result: all pass.

## Phase Risks and Mitigations

- Risk: the ledger carry surface is large and easy to miss a checkpoint path.
  Mitigation: mirror every `organization_operations` carry site listed in
  Current-Code Evidence and add a perspective→snapshot→checkpoint round-trip
  test before any analysis work.
- Risk: peer frames could manufacture expectations.
  Mitigation: communicated claims are retained with lower trust, role
  recognition requires objective office/organization refs, and no frame can
  mint a venue belief by itself.
- Risk: attendance could become a hidden path planner.
  Mitigation: one-hop `Move` only through an observed exit, one deterministic
  candidate, and no `Transport`/`Flee` compilation.

## Phase Completion Checklist

- Every Task 1-4 acceptance criterion is verified.
- `markets_credit` is owned; four flags remain unowned.
- No new command, event, observer semantic type, write pair, runner schema,
  `/v2` route, or migration exists.
- `index.md` task checkboxes are updated immediately after verified completion.
