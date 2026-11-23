# Phase 3: Replay and visibility

Plan: [index.md](index.md)  
Tasks: 5–7  
Depends on: Phase 2

## Objective

Persist exact net effects with the reserved 25/`v23` pair, prove historical reads and trusted objective continuation, and retain existing agent and observer wire surfaces.

## Current-Code Evidence

| Path | Symbols | Why it matters |
|---|---|---|
| `src/simulation/versioning.py`, `src/simulation/persistence.py` | `V4_WRITE_PAIR_RESERVATIONS`, `checkpoint_schema_for_production`, `schema_projector_compatible` | Reservations do not activate writers; selection is explicit and priority-based. |
| `src/world/events.py`, `src/simulation/serialization.py`, `src/world/_replay.py` | detail/schema registries, `_encode_event_details`, `_decode_event_details`, `_encode_world_event`, `_prepare_events`, `_apply_event_effect` | New detail must be closed to its own envelope; inherited events still use their established shapes. |
| `src/simulation/journal.py`, `src/simulation/service.py`, `src/simulation/runner.py` | `_encode_world_snapshot`, `_decode_world_snapshot`, `bind_snapshot_commit_hash`, `draft_checkpoint_from_candidate`, `resolve_tick`, `_bootstrap_snapshot`, `_engine_snapshot` | Bootstrap/checkpoint/fork and caller-snapshot comparisons must agree on pair and channel bytes. |
| `src/simulation/replay.py`, `src/simulation/engine.py` | `_replay_bounded`, `restore_from_snapshot`, `restore_from_verified_batches`, `select_checkpoint_schema` | History folds without policy; live objective continuation must be trusted. |
| `src/api/observer_replay_context.py`, `src/api/persistence_services.py`, `src/simulation/replay.py` | `PersistenceObserverReplayContextSource.read_context`, `SimulationReplayRequest`, `_replay_request` | Existing API readers do not supply environmental dynamics to replay. V23 must be self-contained for historical seasonal facts. |
| `src/world/_perception.py`, `src/observer/adapt.py`, `src/api/observer_service.py`, `src/api/routes/observer_stream.py` | `_project_event_window`, `is_hidden_observer_event`, observer detail/list/tick/stream reads | Drop internal capacity effects before audience or observer page construction. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/world/events.py`, `src/world/__init__.py`, `src/world/_replay.py`, `src/simulation/serialization.py` | modify | Register strict replay v25 net effects and inherit v24 detail families without modifying legacy wire versions. |
| `src/simulation/ecological_resources_checkpoint.py` | create | Exact detached section, row codec and validators. |
| `src/simulation/{versioning,persistence,journal,service,runner,engine,replay,bootstrap}.py` | modify | Pair selection, section, verified history and continuation. |
| `src/world/_perception.py`, `src/observer/adapt.py`, `src/api/observer_service.py`, `src/api/routes/observer_stream.py`, `src/persistence/sqlalchemy.py`, `src/persistence/history_archive_filesystem.py` | modify | Hide the ecology transition from presentation; extend existing reader exclusion before limits. |
| `tests/unit/test_ecological_resources_replay.py`, `tests/unit/test_ecological_resources_observer.py`, `tests/integration/test_ecological_resources_durable_replay.py` | create | Pair/codec, exclusion, and durable Postgres proof. |

## Task 5: Register and fold ecology effects

### Intent

Use one replay schema for an active run, including combinations with existing objective channels.

### Implementation Steps

1. Activate reserved `EVENT_SCHEMA_REPLAY_V25 = 25` and codec `v23`. Put ecology first in `checkpoint_schema_for_production` and pass active state at every `select_checkpoint_schema` and selector caller. Schema 25 admits all event families admitted by 24 (including measurement and travel) plus ecology; 25 does not add any event to earlier versions. Use the established occurrence wire shape, not a new envelope.
2. Register `EcologicalResourceChanged` in exact event detail allowlists, `world.__all__`, JSON encode/decode, system-family and entity/origin matching. Enforce a system regeneration cause, matching resource ID and actual node location when applying the effect. Wire keys are exactly `kind`, `resource_id`, `before_damage_tenths`, `after_damage_tenths`; `kind` is `ecological_resource_changed`. Type/range checks reject bool, no-op and unknown fields.
3. In `world._replay._apply_event_effect`, verify active channel, selected row and matching `before_damage_tenths`, validate `after` against `base-floor` and current stock, and replace only damage. For `ResourceRegenerated` on a managed node verify strictly positive recorded delta equals the actual before/after difference on the tenths grid and result stays under effective capacity. Do not rerun pressure, season, infrastructure logic or RNG. Unmanaged event handling stays unchanged.
4. Route accepted v25 through `_prepare_events`, `schema_projector_compatible` and every closed dispatcher currently gating event v24, including commit/journal verification. Do not rank schemas by numeric value. Legacy 24/`v22`, 27/`v25` and 28/`v26` remain selected exactly as before when ecology is absent.

### Required Interfaces and Contracts

- One pair per active run; no compatibility changes for old pairs. Source: `.ai-factory/ROADMAP.md` → M8; `src/simulation/versioning.py` reservation; `.ai-factory/ARCHITECTURE.md` → Versioned Extension Contract.
- Event carries capacity state only; ordinary command and regeneration events are the only stock mutations.

### Error Handling and Logging

Reject unknown pair, invalid cause, wrong origin, unknown resource, mismatched `before` and bad cap as invalid event/fold errors with stable reason codes; no event/policy payload logs.

### Tests

`tests/unit/test_ecological_resources_engine.py`: now resolve a real in-memory tick with two ordered withdrawals, failed/denied attempts, resource-backed vs held-item drinking, and a separate alternate debit. Confirm local next-observation stock, no extra random draws, and legacy event bytes in the existing environment case. `tests/unit/test_ecological_resources_replay.py`: exercise exact event encode/decode, reject ecology in old envelopes, reject malformed/misordered effects and impossible regeneration, fold from an in-memory bootstrap through a multi-tick trace without an ecology policy, and compare stock, damage, event order and canonical observations at each boundary. Task 6 owns checkpoint and durable pair tests, including commit failure without publication.

### Acceptance Criteria

V25 replay can reconstruct capacity and quantity without policy; the old v24–28 feature pairs keep their prior selection when ecology is absent.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_ecological_resources_engine.py tests/unit/test_ecological_resources_replay.py tests/unit/test_environmental_dynamics_replay.py tests/unit/test_disease_replay.py -q` passes for in-memory event and fold cases. Add checkpoint cases in Task 6 and rerun the command there.

## Task 6: Round-trip checkpoints and verified continuation

### Intent

Avoid a bootstrap/mid-run mismatch and preserve immutable published history.

### Implementation Steps

1. Add `EcologicalResourcesCheckpointSection` with exact keys `schema_version` (`ecological-resources-checkpoint-v1`), `policy_sha256` (64 lowercase hex characters), and `rows`. Rows are 1–128 sorted `resource_id`, `minimum_capacity_tenths`, `damage_tenths` triples encoded as exact objects. Use the Phase 1 invariants and reject unknown fields, noncanonical order, missing nodes, invalid floor and quantities over cap. Accept section only in v23; require it whenever v23 is selected.
2. In `SnapshotExtensions`, `WorldSnapshot` and journal snapshot encode/decode, build v23 from the v22 compositional shape plus mandatory sibling keys `ecological_resources` and `environmental_dynamics`. Reuse `EnvironmentalDynamicsSpec.canonical_payload` and the strict existing spec decoder in `runner_serialization.py`; do not store the whole runner config or trust plain caller-provided season data. Keep the v22-mandatory disease section conditional in v23. Other inherited sections retain the v22 union's shape and enclosing channel consistency checks. Earlier codecs must not accept or encode the new fields. Include both siblings in the canonical snapshot/commit binding. Add no SQL column, index or migration.
3. Carry the ecology state into `WorldBootstrap` and assemble typed v23 checkpoint extensions from the same source state in the runner and service. Cover both draft and final snapshot construction in `_engine_snapshot` and `draft_checkpoint_from_candidate`, `service.resolve_tick`'s caller-normalized snapshot, and both copies in `journal.bind_snapshot_commit_hash`. Prefer `dataclasses.replace` for the new v23 copy paths so future fields cannot silently drop; keep older paths and bytes untouched. On v23, each active inherited channel is carried consistently from bootstrap through checkpoints. A fast unit test must exercise candidate creation, encode/decode, hash binding and restore, not just an event fold.
4. Thread trusted ecology spec through `ReplayRequest`, both `ReplayService` restore call paths, and `WorldEngine.restore_from_snapshot` / `restore_from_verified_batches`. Use the verified v23 snapshot's environmental dynamics to restore seasonal observations and detached observer facts; if a trusted in-process environment spec is also supplied, require its digest to match. Older codecs retain their existing context behavior. Without ecology policy, permit historic fold/observation only; resolving and direct population/kinship mutations must fail before any candidate/state mutation. With policy, require matching digest and row IDs/floors. Thread matching policy through existing exact in-process continuation paths; no public policy parameter or full subjective/API restart.
5. From a real Postgres-backed v60 run, persist bootstrap and intermediate checkpoints plus a tail; reopen via verified replay with the matching policy and append the next ordinary tick with the previous commit hash. Compare stock, damage and continued event bytes with an uninterrupted twin. Also restore with no ecology policy, checking seasonal data through the existing historical replay/observer paths; verify mismatch rejection, stable old hashes, and a failing durable tick that publishes neither state nor events.

### Required Interfaces and Contracts

- `WorldSnapshot` and replay models remain detached public contracts; private stock map is not imported by persistence. No API manager restart feature or branch-history rewrite.
- `.ai-factory/ARCHITECTURE.md` → append-only history; `docs/v4-migration-sequence.md` reserves ecology SQL only for proven indexed need, which this feature does not have.

### Error Handling and Logging

Use stable `ecology_policy_required`, `ecology_policy_mismatch`, `ecology_checkpoint_invalid`-style codes and metadata-only DEBUG/ERROR as appropriate. Required-but-missing channels, wrong pair and bad hashes fail closed atomically. Do not log digest input, raw rows or credentials.

### Tests

Unit replay tests add canonical bootstrap/mid-run round trip, matching season across a boundary without adding API replay context, rejection of supplied conflicting season spec, read-only versus trusted continuation, missing/extra rows, both checkpoint copy paths with hash binding, mixed-section candidate/fork checks, and tampering failures. `tests/integration/test_ecological_resources_durable_replay.py` follows the existing durable replay pattern for event store, checkpoint store and separate trusted continuation runs. Preserve checkpoint integrity test coverage.

### Acceptance Criteria

Reopening exactly preserves objective state, observation and continued effects; no migration beyond `0017`.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_ecological_resources_engine.py tests/unit/test_ecological_resources_replay.py tests/unit/test_environmental_dynamics_replay.py tests/unit/test_disease_replay.py -q`; then with repository-approved disposable `PALIMPSEST_TEST_DATABASE_URL`, `uv run --frozen --python 3.12.14 pytest -m integration tests/integration/test_ecological_resources_durable_replay.py -q`. A skipped database lane must be recorded as unexecuted, not passed.

## Task 7: Keep new internal transitions off presentation surfaces

### Intent

Expose only the ordinary effects already visible to agents and observers, without expanding or leaking through the protocol.

### Implementation Steps

1. In `world._perception._project_event_window`, drop ecology effects before audience classification; agent-facing local stock and season remain visible only via the existing rules.
2. Add ecology to the hidden observer detail set in `observer.adapt`; retain the disease exclusion. Pass the closed multi-kind exclusion through observer lists, ticks and WebSocket catch-up/live reads. In `ReplayService.read_event_keyset_page`, combine optional singular and plural values into an exact set. Push that set to SQL/archive before `limit + 1`; when the reader has no plural support, use `_exclusive_scan` with the same set in `_matches_filters`. Advance only a private `(tick, sequence)` cursor across hidden rows; exposed page cursors derive from visible rows. Preserve existing scan budget and `observer_read_budget_exhausted` error if exhaustion prevents determining the page; never turn that into false EOF. Keep unfiltered objective reads and event folds unchanged. Existing detail lookup returns not found for hidden events.
3. Ensure ordinary folded quantity and regeneration presentation work in the same read-only clients; no new observer type, alias, fields, overlays, or protocol version.

### Required Interfaces and Contracts

- World raw exports/events remain complete; observer readers do not silently fail or return empty pages because a hidden record filled the limit.
- Source: `.ai-factory/ARCHITECTURE.md` → Memory, testimony, and subjective concepts; read-only clients and historical compatibility.

### Error Handling and Logging

Reject direct adaptation of a hidden event through the existing closed behavior; limit logs to kind/reason and existing safe identifiers. No policy or damage in hints, stream payloads, or logs.

### Tests

`tests/unit/test_ecological_resources_observer.py`: pattern from `tests/unit/test_disease_observer_redaction.py`; include mixed hidden kinds across live stream, catch-up, historical and direct detail reads, ticks/frames, and objective inspection. With a test double that accepts no plural filter, put a hidden-only batch before visible rows; assert the next visible page and cursor, then exceed the unchanged budget and assert explicit exhaustion. Assert an owner at the node receives local folded quantity but no ecology event or row. Exercise SQL/archive query filtering in the durable test and reader unit tests.

### Acceptance Criteria

Observer pagination and stream resume still reach the same visible records and public semantics remain 73; raw objective replay still contains both hidden kinds when present.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_ecological_resources_observer.py tests/unit/test_disease_observer_redaction.py tests/unit/test_environmental_dynamics_observer.py -q` passes.

## Phase Risks and Mitigations

- Pair/resume drift: assert the chosen pair at all boundaries and fold a verified tail before continuation.
- Internal events swallowed after a short page: test pre-limit exclusion through storage and replay, not only adapter rendering.

## Phase Completion Checklist

- Replay, digest, read-only, trusted continuation, and both visibility surfaces verified; record real integration status and update only verified checkboxes in `index.md`.
