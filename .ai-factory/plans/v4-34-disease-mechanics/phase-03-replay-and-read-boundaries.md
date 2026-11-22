# Phase 3: Effect-complete replay and redacted reads

Plan: [index.md](index.md)  
Tasks: 5–6  
Depends on: Phase 2 / Tasks 3–4

## Objective

Persist the hidden channel in existing durable envelopes, restore it exactly, and prevent objective disease records from entering agent and presentation projections.

## Current-Code Evidence

| Path | Symbols / sections | Why it matters |
| --- | --- | --- |
| `src/simulation/versioning.py`, `src/simulation/persistence.py` | Epidemics reservation, `checkpoint_schema_for_production`, `WorldSnapshot`, `SnapshotExtensions` | Reserved pair and exact per-run versions |
| `src/world/events.py`, `src/world/_replay.py` | `require_replayable_event`, `_prepare_events`, `_apply_event_effect` | Exact accepted sets and effect application |
| `src/simulation/journal.py`, `src/simulation/engine.py`, `src/simulation/service.py` | `bind_snapshot_commit_hash`, `_decode_world_snapshot`, `_BatchRestoreBuilder`, `draft_checkpoint_from_candidate` | Hashing and full/bounded restore |
| `src/simulation/persistence.py`, `src/simulation/replay.py` | `WorldSnapshot.config`, `ReplayRequest`, `ReplayService.open_durable` | World replay config is not the serialized runner config; continuation has a separate gate |
| `src/observer/adapt.py`, `src/api/observer_service.py`, `src/api/routes/observer_stream.py` | `adapt_event`, `adapt_events`, list/tick/detail reads and `ObserverStreamSession` | Filtering before adapter/visible pagination |
| `src/api/routes/streams.py`, `src/api/streaming.py` | `OBJECTIVE_INSPECTION`, `StreamFanout` | The ordinary run stream is a separate authorized objective lane |
| `src/simulation/replay.py`, `src/persistence/sqlalchemy.py`, `src/persistence/history_archive_filesystem.py` | `read_event_keyset_page`, `list_events_keyset`, canonical snapshot graph | Existing query and authoritative state storage seams |

## Files to Change

| Path | Action | Responsibility |
| --- | --- | --- |
| `src/simulation/disease_checkpoint.py` | Create | Neutral canonical disease checkpoint rows and exact field validation |
| `src/world/events.py`, `src/world/effects.py`, `src/world/_replay.py`, `src/simulation/serialization.py` | Modify | Version-gated transition, death/family wire checks, apply recorded effects |
| `src/simulation/persistence.py`, `src/simulation/journal.py`, `src/simulation/runner.py`, `src/simulation/service.py`, `src/simulation/engine.py`, `src/simulation/compatibility.py`, `src/simulation/replay.py` | Modify | Select, encode, validate and restore both checkpoints and journal tails |
| `src/observer/adapt.py`, `src/api/observer_service.py`, `src/api/routes/observer_stream.py`, `src/persistence/sqlalchemy.py`, `src/persistence/history_archive_filesystem.py` | Modify | Consistent redaction and cursor-safe filtered reads |
| `tests/unit/test_disease_replay.py`, `tests/unit/test_disease_observer_redaction.py` | Create | Proof of compatibility, effect parity and boundary behavior |

## Task 5: Activate reserved replay 24 and checkpoint codec v22

### Intent

Enable a single exact pair for disease-active runs and replay recorded effects without re-running a random decision.

### Implementation Steps

1. Add explicit accepted schema 24 and codec `v22`; leave 25/`v23` and 26/`v24` unaccepted. In `checkpoint_schema_for_production` select disease first; all lower/higher existing channel priorities remain unchanged when off. Schema numbers are not capability order. For 24 explicitly accept every event family supported on 28 and retain the existing per-event validation, plus disease effects and the new disease death cause/family. Treat v22 as the explicit union of v26's active feature extensions plus `disease_mechanics`, using its presence condition rather than numerical ordering. Do not admit disease payloads into 23/27/28 or change accepted legacy payloads. Audit strict schemas and the fast dispatch paths, not just the enum.
2. Add `DiseaseStateChanged` with exact fields `body_id`, nullable `before`, nullable `after`; rows carry closed phase, deadline when required and symptom only when active. Reject equality, duplicate effects for one body in a tick, and invalid transitions. For a living body accept only absent → latent, latent → active, or active → absent/immune; for a body already dead in this fold accept only existing row → absent. This is a net effect, not telemetry of intermediate states. Replay sees ordinary `Died` before removals. No transmission source or contact graph in event payload. Keep trusted transport detached from `world._disease`.
3. Add a v22-only mandatory `disease_mechanics` checkpoint section with exactly `rows` (sorted unique, empty valid) and `policy_sha256` (hash of the exact canonical `DiseaseMechanicsSpec` encoding from Task 1, including its version and founder assignment). Store no duplicate policy or RNG state. Other codecs reject the section. Preserve it and its digest in `_engine_snapshot`, `draft_checkpoint_from_candidate`, `bind_snapshot_commit_hash`, `branch_service.rematerialize_snapshot`, and initial/cadence snapshot paths. Where both snapshot and manifest are available, check the exact schema/codec pair agreement before folding.
4. Fold recorded effects in `_apply_event_effect`, require each before value to match, and validate deadlines and living owners at the finalized boundary. Both `WorldEngine.restore_from_snapshot` and `restore_from_verified_batches` must reconstruct observations without running the policy or needing the full runner config. For objective continuation, let a trusted caller supply the typed spec on the internal `ReplayRequest`; when reading a persisted v58 runner config, verify its existing record fingerprint before decoding and pass only the spec. Validate the spec against the snapshot's `policy_sha256` before installing it. Without a spec, return a read-only result even at the head, and reject objective tick preparation and `open_durable`. An explicitly supplied mismatched spec fails closed. Never reseed initial rows during restore or accept a policy override from HTTP. `recover_pending_finalizations` is not full process-loss runner recovery; no new subjective recovery path. Reuse canonical JSON storage; no migration.

### Contracts / evidence

- `simulation.versioning` reserves this pair; `world._replay` rejects mixed schemas; M8 requires effect-complete restoration and a demonstrated migration trigger. Malformed records, version mismatch, partial disease sections and unexpected before values use existing safe codec/replay errors. Log only version, tick, and reason code.

### Tests, acceptance, and verification

- In `tests/unit/test_disease_replay.py` prove strict round trips; reject old-schema disease keys/new death cause, 25/26, invalid before values and duplicate net effects. Verify enabled-empty snapshots, candidate persistence failure without live state/cue publication, and full and bounded history restores without a policy. Patch the live decision function to raise during fold. Verify missing/mismatched policy prevents continuation; a verified one agrees with uninterrupted execution. Test all four inherited travel/instrument combinations on 24/`v22` and representative infrastructure-only 23, travel-only 27, and measurement-only 28 fixtures.
- Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_disease_replay.py tests/unit/test_persistent_simulation_service.py tests/unit/test_v4_versioning_reservations.py tests/unit/test_checkpoint_restoration.py tests/unit/test_travel_network_replay.py tests/unit/test_measurement_replay.py -q`. Acceptance: each allowed combination has one pair, verified restore matches live, and legacy bytes are unchanged.

## Task 6: Redact internal transitions across observer reads

### Intent

Keep observer-semantic count and protocol unchanged; no list, frame, detail, stats or stream may leak private transitions or diagnostic death payloads.

### Implementation Steps

1. Add one observer presentation predicate in `observer.adapt` with a single exclusion for `disease_state_changed`. Use it in `adapt_events` and all direct callers of `adapt_event`. Refuse adapting the private event directly; keep the existing sanitized death presentation. Apply the same policy to event rows and projection-derived tick summaries/counts, including local/archive sources, and return `observer_event_not_found` for direct lookup of a hidden event.
2. For observer HTTP list, tick summaries and WebSocket, add optional `exclude_event_type` to the replay keyset query and its SQL/archive implementations; apply it before `limit+1` and after other equivalent query filters. Use one bounded exclusive scan for in-memory/no-keyset adapters: advance a private last-read cursor, continue through hidden-only batches, and return the existing safe read-budget failure rather than false exhaustion. Do not allow the fallback `TypeError` retry to return unfiltered data. Keep objective reads unfiltered. For tick summaries query visible rows in the requested tick range before limiting; for list results keep the last returned visible event as the only client paging cursor.
3. Change the internal `ObserverStreamSession` reader result to carry visible rows and verified exhaustion for the range through a pinned committed head. Continue reading when a completed run still has another visible page. Only send completion after the pinned range is exhausted; if its suffix is hidden-only, reuse the last visible cursor already sent (or the original subscription cursor) and never promote the private scan cursor into the response. Keep the wire schema and committed visible sequences. Preserve the separately `OBJECTIVE_INSPECTION`-gated raw outbox (`api.routes.streams` / `api.streaming`) and objective event route; do not apply observer filtering to these trusted reads. Strip disease cause/family from ordinary observer death and local occurrence projections; add no new route or grant.
4. After the read-boundary tests pass, enable the public `SimulationRunner.from_config` disease activation path. Until this step, keep a fail-closed activation guard and exercise the new pair through trusted test composition only.

### Contracts / evidence

- `.ai-factory/ARCHITECTURE.md` separates owner projection, objective inspection and observer presentation. Existing read budgets and cursors must not be weakened. Keep DEBUG page metadata limited to visible counts and safe reason codes; never dump hidden records, locations or IDs.

### Tests, acceptance, and verification

- In `tests/unit/test_disease_observer_redaction.py`: mix visible/internal rows before, between and after visible events; cover a hidden-only page, hidden-only trailing tick, HTTP pagination, filter/detail/tick-summary, historical/live frame, and completed WebSocket with more than one batch plus a hidden-only suffix. Assert all remaining visible events precede completion, no private cursor/cause payload appears, and authorized raw inspection/outbox still returns the recorded objective rows. Reuse existing observer authority and stream fixtures.
- Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_disease_observer_redaction.py tests/unit/test_observer_stream.py tests/unit/test_observer_authority.py -q`. Acceptance: identical projection rules across surfaces, correct original cursor progress and no protocol or semantic-count change.

## Phase Risks and Mitigations

- Numeric version comparison would accidentally admit reserved pairs or omit inherited measurement/travel payloads. Use explicit capability/version sets.
- Filtering a page only after adaptation can throw or misreport end of history. Filter before page limiting and exercise hidden-only boundaries.

## Phase Completion Checklist

- Verify Tasks 5–6 and update only `index.md` progress after each success.
