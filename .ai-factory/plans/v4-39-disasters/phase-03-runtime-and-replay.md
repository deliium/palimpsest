# Phase 3: Runtime, Replay and Recovery

Plan: [index.md](index.md)  
Tasks: 4  
Depends on: Phase 2 / Tasks 2–3

## Objective

Activate the reserved pair with effect-complete, fail-closed replay. A live tick, a verified checkpoint continuation, and a historical fold must agree without granting the projector access to the policy or RNG.

## Current-Code Evidence

| Path | Symbols | Why it matters |
|---|---|---|
| `src/simulation/engine.py` | `_resolve_ordered`, `_apply_disease_pass`, `select_checkpoint_schema`, `restore_from_snapshot` | Tick order, private trailing disease effects, restore and atomic commit. |
| `src/simulation/bootstrap.py`, `src/world/_state.py` | `WorldBootstrap`, `_materialize_world`, `rebuild_world_state` | Objective state validation and active/off distinction. |
| `src/simulation/persistence.py`, `src/simulation/service.py`, `src/simulation/runner.py` | `checkpoint_schema_for_production`, `WorldSnapshot`, `draft_checkpoint_from_candidate`, `_engine_snapshot` | All write selectors and snapshot assembly paths must agree. |
| `src/simulation/serialization.py`, `src/simulation/journal.py`, `src/world/_replay.py` | `required_domain_schema`, event and snapshot codecs, `_prepare_events`, `_project_tick_group` | Exact allowlists, mixed-version rejection and pressure special cases. |
| `src/simulation/replay.py`, `src/simulation/engine.py` | `ReplayService`, `restore_from_snapshot`, `restore_from_verified_batches`, `_BatchRestoreBuilder` | Non-batched and streaming recovery restore through separate entry points. |
| `src/world/_perception.py`, `src/observer/adapt.py` | prior event filtering, `HIDDEN_OBSERVER_EVENT_TYPES` | Private effects must never enter agent or public event audiences. |
| `src/persistence/inspection_sqlalchemy.py`, `src/persistence/debugger_sqlalchemy.py` | `SqlAlchemyObjectiveEvidenceLoader.load_events_page`, `SqlAlchemyDebuggerEventLookup` | Paging selects `limit + 1` rows before decoding; both debugger address forms query persisted rows directly. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/world/events.py`, `src/world/effects.py`, `src/world/_disasters.py`, `src/world/_state.py`, `src/world/_replay.py` | Modify | Closed event, objective binding, reducers/fold, tranche checks and canonical state. |
| `src/simulation/bootstrap.py`, `src/simulation/engine.py`, `src/simulation/runner.py`, `src/simulation/service.py` | Modify | Bind policy before live use and restore, run candidate effects, export matching checkpoint payload. |
| `src/simulation/replay.py` | Modify | Pass trusted optional policy into both restore paths and map known incompatibility codes consistently. |
| `src/simulation/persistence.py`, `src/simulation/journal.py`, `src/simulation/serialization.py`, `src/simulation/versioning.py`, `src/simulation/compatibility.py`, `src/simulation/runner_models.py` | Modify | Pair dispatch, ownership, accepted sets, exact event and snapshot shapes. |
| `src/world/_perception.py`, `src/observer/adapt.py` | Modify | Suppress new objective receipts before any audience/semantic classification; no protocol extension. |
| `src/api/observer_service.py`, `src/api/routes/observer_stream.py`, `src/api/routes/inspection.py`, `src/api/routes/replay.py`, `src/api/routes/debugger.py` | Audit and modify only uncovered filters | Prevent new private receipt metadata from leaking through direct API paging, by-ID/cursor, replay summaries or stream delivery. |
| `src/api/persistence_services.py`, `src/simulation/inspection.py`, `src/persistence/inspection_sqlalchemy.py`, `src/persistence/debugger_sqlalchemy.py` | Modify | Pass the exclusion into the keyset query and deny both debugger addresses without affecting journal access. |
| `tests/unit/test_disaster_replay.py`, `tests/unit/test_disaster_checkpoint.py`, `tests/unit/test_disaster_privacy.py` | Create | Live/fold equivalence, checkpoint continuation, malformed payload and no-leak coverage. |
| `tests/unit/test_v4_versioning_reservations.py`, `tests/unit/test_v4_scaffolding_gate.py`, `tests/unit/test_runner_config_v56.py`, `tests/architecture/test_v4_architecture_invariants.py` | Modify affected assertions | Own reservation without raising maxima; old roots still cannot run the flag; no other authority change. |

## Task 4: Activate objective execution and effect-complete replay

### Intent

Make each resolved candidate atomic and replayable, with no changes to prior frozen runner/checkpoint bytes or flags-off behavior.

### Implementation Steps

1. Add a frozen private disaster state document with exact keys `policy_sha256`, `overexploitation_active`, `applied_rule_ids` under checkpoint key `disaster_state`. The digest is lowercase SHA-256 of the canonical policy object, `overexploitation_active` is a strict bool, and the tuple of applied IDs is sorted unique with at most 32 entries. State is `None` when off; active starts with `()`. Bind the pressure flag and digest from the validated runner/bootstrapped policy, not from inference on later events. Preserve state through all rebuilds and stage it in the objective candidate, not in an engine-owned mutable ledger. No snapshot/state keys are added to earlier codecs.
2. Bind the active policy at `SimulationRunner.from_config`, materialization, and restore. At the start of `_resolve_ordered`, compute due candidates once from the immutable policy, absolute open tick, and existing applied IDs. Preserve existing ordering except for the new stages: ordered actions, arrivals and completed production, infrastructure decay, ordinary physical/weather/renewal, stock and infrastructure shocks, ordinary route recomputation, fictional disease with optional surge callback, existing lifecycle/cleanup/repository events, private disease net changes, then surge receipts. Publish all effects and consumed bits only with the ordinary tick commit. The disease applied bit counts only a finalized additional latent entry. A skip receipt is not a semantic state mutation; preserve existing revision semantics.
3. Add `DisasterResolved` (wire kind `disaster_resolved`) and `SystemEffectFamily.DISASTER` using deterministic `derive_system_cause_id` with target entity ID and a single increasing in-tick disaster family ordinal in emission order. Receipt common fields: `rule_id`, `kind`, `origin`, typed `target`, closed `outcome`, and discriminated `effect` below. Use ordinary committed event tick, sequence, and revision; no second clock. Out-of-scope metadata such as future schedule, config document, user labels and RNG internals never enters events. Add the new receipt only to event 26 / codec `v24` and use projector `v2`.

   | Receipt outcome and kind | Effect and projector action |
   |---|---|
   | Applied stock | Exact quantity/damage before/after in tenths; reducer checks target, kind/weather, before-state and clamps; fold both atomically, then mark rule applied. For a positive-to-zero crossing require the immediately following matching `ResourceNodeDepleted` witness; witness uses the existing resource-node family and contributes no second mutation. |
   | Applied infrastructure | Resolved `asset_id`; immediately preceded by matching `InfrastructureDestroyed` under a DISASTER system cause for the same target asset. Fold the standard event once; check transition/correlation before marking applied. Existing ordinary infrastructure events use their former causes and do not require receipts. |
   | Applied surge | Only `additional_latent_count`, positive; requires active fictional disease, same-tick local finalized absent-to-latent net rows sufficient for the claim, one surge receipt per location per tick, and last/private tranche. Mark applied; do not write disease rows from receipt. |
   | Skipped scheduled | Null effect; outcome exactly `weather_ineligible`, `no_effect`, `no_live_asset`, or `asset_ambiguous` as applicable; no advance of applied IDs. No spontaneous skip event. |

4. Add `disasters_active` to all shared selectors; prioritize it over other active channels. Fill event 26 / `v24` without increasing accepted maxima (29 / `v27`). For the new pair, use the complete permitted codec union of the executable v60 family and its explicitly allowed optional siblings: carry infrastructure/travel/measurement/disease and either ecological change or pressure according to binding, not numerical comparison. Keep older keysets and event branches unchanged. Snapshot `v24` inherits the keyed ecological shape and permitted optional channels, plus exactly `disaster_state`; this root is invalid without ecological state/digest. A legacy codec with any disaster fields is invalid. For v24 only, use presence of the existing `infrastructure` / `travel_network` keys as explicit active bindings: omit when inactive, encode `[]` when active-empty, reject null, and require infrastructure and the ordinary region/journey binding when travel is present. Feed these bindings into `_bind_infrastructure_networks_channel` and `_bind_travel_network_channel`; do not apply the legacy codec or `bool(rows)` inference to v24. Require runner `_engine_snapshot` and service `draft_checkpoint_from_candidate` to agree with those semantics, including first and idle checkpoints. Verify other inherited channel sections against their own active state and keep the old codecs' selection untouched.
5. Extend replay's complete and prefix paths, apply effect details rather than rolling or calling the policy, and reject unsupported effect variant, duplicate rule within a tick, applied-rule reuse, mixed versions, wrong origin/cause, missing companion, reordered tranche, mismatched before values and unknown targets. For prefix folds that can legally end between a companion and receipt, admit only the existing partial-boundary semantics: no publishable completed boundary or restorable checkpoint until the companion/receipt pair and tick are finalized. Switching to event 26 must not weaken `_project_tick_group` pressure checks: activate the pressure branch from `disaster_state.overexploitation_active` for 26, require pressure and immediate renewal witnesses exactly as in 29, forbid ecological standalone change in pressure mode, and never charge later stock-shock losses as withdrawals. For nonpressure mode, allow the same ecological changes as 25 and forbid pressure. Retain existing per-sibling validity checks.
6. Make `ReplayRequest` carry an optional trusted disaster policy, never accepted as a new public API parameter. Forward it through both `ReplayService` paths to `WorldEngine.restore_from_snapshot` and `restore_from_verified_batches`, retaining the binding and applied ledger through `_BatchRestoreBuilder`. For event 26 with no supplied policy, restore in inspection-only mode for disasters: objective history and observations remain readable without any disaster draws. Reject advancing via `resolve_tick` or an equivalent prepared/durable path, and reject other public objective mutations on that unbound restored engine before any work or state change. With a supplied policy, validate the exact digest, applied-ID membership, and pressure binding against trusted sibling configuration; on mismatch, fail with `disaster_policy_mismatch` and map it to `VERSION_INCOMPATIBLE` in both replay branches. Reject a supplied disaster policy on a legacy/off snapshot. Preserve legacy restoration and preexisting sibling policy requirements. Restore the same absolute clock, so a previously due entry cannot be injected twice.
7. Add receipt filtering before agent-event classification and to observer stream/durable inspection exclusion, including event-detail lookup and direct adapter handling using the existing hidden-event pattern. For metadata-only generic inspection, pass a `disaster_resolved` exclusion from `PersistenceInspectionService.events_page` through the objective evidence port into `SqlAlchemyObjectiveEvidenceLoader.load_events_page`; filter on `WorldEventOrm.event_type` in the query before `limit + 1`, `has_more`, and cursor construction. Do not retrofit this new exclusion into unrelated readers by default. For `SqlAlchemyDebuggerEventLookup`, treat a receipt as missing for both `get_by_event_id` and `get_by_tick_sequence` before returning a debugger record; preserve existing not-found translation. Redact any disaster state from public replay DTOs while retaining trusted, unfiltered journal access for hash verification. Keep the surge receipt after private disease transitions so it doesn't shift earlier visible sequence positions. Verify ordinary physical quantities and infrastructure still project with no new observation kind. Update both owned allowlists; leave old schema gating explicit.

### Required Interfaces and Contracts

| Selected configuration | Live writes and checkpoint/fold contract |
|---|---|
| Disasters off; all legacy combinations | Exact prior event, codec, projector and key selection; no disaster state/draws. |
| v63 ecology without pressure | 26 / `v24` / `v2`; state pressure flag false; ecology net changes allowed; pressure receipts rejected. |
| v63 with overexploitation, with or without commons governance | Same pair; flag true, existing pressure and renewal requirements; commons pending remains v7 where selected. |
| Either v63 row plus already-compatible infrastructure/travel or measurement | Same pair, optional rows and event families validated under existing semantics. Infrastructure shocks require the enabled channel; routes update through existing recalculation. |
| Either v63 row plus fictional disease, with or without medical beliefs | Same pair, active disease binding and private net rows required for surge; unchanged owner-only observation and existing subjective pending version selection. |
| Inert, scheduled-only, spontaneous-only, or a mixture of disjoint rules | Same v63 pair even if no shock occurs. Existing tick commit mechanics and immutable state apply; do not fabricate receipts for future/never-executed ticks. |

- For event 26, retain accepted inherited event shapes without broadening their allowance on any old pair. Validate with explicit feature membership and subdocument presence, never greater-than version arithmetic. Do not serve `disaster_rows`, add a command/overlay/route, or conflate this objective feature with subjective pending versions.
- Migration-plan stage `v4-m05-disaster-state` still requires proven indexed query need; actual durability here uses existing journal/snapshot payloads. Do not add a SQL migration.

### Requirement Evidence

- `versioning.py` reserves `26/v24` for effect-complete objective disaster onset/effects. M8 calls for an evidence-gated replay/migration trigger. The reservation adds a codec pair, not a reason for new relational storage.
- Effect recording, strict per-feature compatibility, append-only atomicity and privacy are constrained by `.ai-factory/ARCHITECTURE.md` and `RULES.md`. The Original Request's seed requirement applies to live simulation and continuation; fold is deliberately RNG-free.

### Error Handling and Logging

- Fail copy-on-write before publish on invalid boundary, companion or typed effect. Wrap replay validation as the appropriate existing projection error code; fail live continuation on policy or seed/identity binding mismatch. Log event schema, safe failure code and aggregate counters only; exclude raw documents, rule/participant identities, symptom state and disease receipt quantities.

### Tests

- `test_disaster_replay.py`: exact event round trip; reject receipt on every other pair and foreign schema on the new pair; invalid union shape, ordering, repeated rule, missing companion, quantity/damage mismatches, privacy tranche and ecological conservation; full/prefix fold with mixed kinds, multiple locations and pressure/renewal probes including next tick; no draw invocation during replay.
- `test_disaster_checkpoint.py`: initial/idle/candidate/export checkpoint parity and journal round trip; independently exercise non-batched and bounded `ReplayService` restore with checkpoint and tail across before/due/after boundaries. Both must support policy-free inspection, reject unbound mutation, and restore identical observations and matching-policy next-tick effects/hashes. Probe changed policy, an off checkpoint with a supplied policy, applied-ID mismatch, and active-empty versus absent infrastructure/travel keys. Verify stable legacy golden docs, scheduled skip, all selection matrix rows and one combined sibling fixture. Inject a commit failure through existing in-memory test ports and verify no applied bit, effects, or consumed schedule persist if objective commit fails.
- `test_disaster_privacy.py`: through production services/adapters (using the existing DB/session test boundary), interleave private receipts and visible rows across two `limit=1` keyset pages; assert no private row influences counts, next cursor or false empty pages. Deny both debugger address forms while returning visible neighbors. Assert journal replay still sees/hashes the hidden rows. Also cover perception, observer batch/lookup and stream, restored/live observations and payload-safe logs/presentation.
- Reuse the v62 commons checkpoint suite (including subjective v7), ecology/overexploitation/disease replay and tests that enforce flags-off behavior. Preserve old maxima and the former unowned rejection tests as equivalent v56/v62 no-spec failure probes.

### Acceptance Criteria

- All writer paths select the same exact pair and new active state; old writer paths are unchanged. Checkpoint-resumed twins and uninterrupted runs agree. A replayed shock never needs live policy, and ordinary clients/cognition see only previously authorized physical consequences.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_disaster_{replay,checkpoint,privacy}.py tests/unit/test_{ecological_resources,disease,overexploitation}_replay.py tests/unit/test_overexploitation_checkpoint.py tests/unit/test_commons_governance_{config,checkpoint}.py -q`
- `uv run --frozen --python 3.12.14 pytest tests/unit/test_v4_{scaffolding_gate,versioning_reservations,migration_plan}.py tests/unit/test_compatibility_matrix.py tests/architecture/test_v4_{architecture_invariants,context_registry}.py -q`

## Phase Risks and Mitigations

- Numeric schema ordering would select an unrelated pair or skip pressure validation. Centralize pair selection and exercise explicit v24 event and snapshot bindings for every applicable sibling.
- A receipt that loses visibility semantics can leak private health evidence. Redact before projection, test observer read paths, and retain trailing private sequencing.

## Phase Completion Checklist

- [x] Task 4 acceptance and verification pass. Mark the Task 4 checkbox only after ordinary and durable replay paths agree.
