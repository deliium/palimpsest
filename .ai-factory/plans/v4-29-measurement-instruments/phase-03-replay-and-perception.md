# Phase 3: Replay and owner-safe perception

Plan: [index.md](index.md)
Tasks: 9–12
Depends on: Tasks 5–8

## Objective

Replay the displayed reading and physical condition exactly, while exposing only eligible display facts to agents and retaining old canonical bytes.

## Current-Code Evidence

| Path | Symbols / evidence | Why it matters |
|---|---|---|
| `src/simulation/persistence.py` | `checkpoint_schema_for_production`, `WorldSnapshot`, accepted sets | Active channel determines event/checkpoint pair. |
| `src/simulation/journal.py` | `_encode_world_snapshot`, `_decode_world_snapshot` | Snapshot fields have codec-gated exact keys. |
| `src/simulation/serialization.py` | `encode_domain`, `decode_domain`, `_encode_command`, `_decode_command` | Top envelope currently schema 1; don't silently widen old observation objects. |
| `src/world/_replay.py` | experiment dispatch near 707 | Replay applies recorded physical effects, not experimental laws or random draws. |
| `src/world/_perception.py` | `_experiment_public_facts`, occurrence projection | Audience filtering must redact hidden instrument transitions. |
| `src/world/observations.py` | `ObservedItem`, `ObservedOccurrence.public_facts`, `Observation` | Typed appearance plus immutable occurrence reading can remain bounded. |
| `src/observer/version.py` | `SEMANTIC_TYPE_BY_KIND`, `EXPERIMENT_RESOLVED` | Coarse scientific-action aliases avoid a protocol/type expansion. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/simulation/persistence.py`, `src/simulation/journal.py`, `src/simulation/serialization.py` | modify | Replay-v28/v26 snapshots and versioned domain envelopes. |
| `src/simulation/measurement_serialization.py` | create | Closed canonical instrument/reference/reading and new-event payload helpers. |
| `src/world/_measurement.py`, `src/world/_replay.py` | modify | Validate and apply recorded transitions without resampling. |
| `src/simulation/engine.py`, `src/simulation/runner.py` | modify | Snapshot creation/restoration and active write selection. |
| `src/world/observations.py`, `src/world/_perception.py` | modify | Gated appearance and participant-only reading projection. |
| `src/observer/version.py`, `src/observer/adapt.py` | modify | Redacted coarse semantic aliases. |
| `tests/unit/test_measurement_serialization.py`, `tests/unit/test_measurement_replay.py`, `tests/unit/test_measurement_perception.py`, `tests/unit/test_measurement_observer.py` | create | Serialization/replay/noninterference/presentation checks. |

## Task 9: Version physical snapshots and strict domain envelopes

### Intent

Persist new authoritative data without changing legacy decoding or reusing an old schema identifier.

### Implementation Steps

1. Add event `EVENT_SCHEMA_REPLAY_V28` and persistence codec `v26` to accepted supported sets; active instrument channel selects that pair ahead of travel/infrastructure/experiment selectors. Absent channel preserves every previous pair.
2. Add `instrument_states` and `measurement_references` to `WorldSnapshot` and journal snapshot encoding only for v26. v26 snapshot keys are the v25 superset plus these two arrays; both are mandatory, possibly empty after item consumption. Reject those keys in older codecs and validate state/item anchors on restore.
3. Audit every explicit schema/codec membership branch in engine, journal and runner checkpoint assembly, including v26 snapshots containing travel/infrastructure fields. Never infer support from a lexical version comparison.
4. Add a domain envelope schema 2, accepted alongside 1. Introduce `required_domain_schema(value) -> int`, a pure recursive selector used before `_encode_top`: inspect direct new commands, measurement event kinds, instrument/reference appearances and measurement occurrences in observations, nested proposal commands, and all export events. Return2 if any contained value needs2; otherwise1. Existing event variants retain their own event schema checks independently. Legacy values still write schema1 byte-for-byte.
5. Pass keyword-only `wire_schema` explicitly from `encode_domain`/`decode_domain` through `_encode_top`/`_decode_top`, `_encode_command`/`_decode_command`, `_encode_proposal`/`_decode_proposal`, `_encode_observation`/`_decode_observation`, `_encode_world_event`/`_decode_world_event`, and `_encode_export`/`_decode_export`. Nested calls inherit exactly the selected parent envelope version; do not rediscover versions independently, infer them from keys, use module globals/contextvars, or let a child silently upgrade an envelope1 parent.
6. In schema2 observation item rows, add optional typed `instrument` and `reference` appearances with strict independent key sets. Legacy rows omit both. A physical item cannot carry both roles. New occurrence reading data is strictly decoded by measurement helpers. Reject measurement fields/tags anywhere under envelope1; reject unknown fields under either version. An old observation without these fields remains valid unchanged.
7. Put leaf codecs in `measurement_serialization.py`; `serialization.py` delegates without logging. Keep domain-envelope version separate from `WorldEvent.schema_version` and journal codec version: `journal.py` currently calls shared event-detail helpers directly. Retain that entry path and gate measurement details on event28/v26, not a nonexistent domain envelope around a journal record. Audit inherited event-detail exact comparisons, notably `route_condition_changed` currently requiring exactly27; permit explicit `{27,28}` where event28 carries that inherited event, while continuing to reject versions lacking its semantics.

### Required Interfaces and Contracts

Events from a measurement-enabled run use replay schema 28 consistently, including existing event variants. This is separate from the domain envelope 2 and pending subjective codec in Phase 5. v22 epidemic codec remains unaccepted. No SQL columns or migrations.

### Error Handling and Logging

Metadata-only `DomainSerializationError(code,path)`; reject duplicate JSON keys, oversized arrays, invalid calibration revisions, malformed scalar/category combinations and new fields in old envelopes. Never log payloads.

### Tests

Canonical roundtrips for all five readings, commands, events, proposals and observations; v26 combined-feature snapshot; old fixtures byte-stable; old/new envelope gating; unknown keys, bool/float in integer slots, non-finite source, nested schema mismatch and oversized records rejected. Put a new command inside an ActionProposal and a new event inside an export, verify parent selection is2, then change only the parent envelope to1 and require rejection. Test observation reference appearance, a replay-v28 inherited route event, and actual journal event-detail encoding without any domain envelope.

### Acceptance Criteria

The new wire contracts are explicit and strict; absent-spec runs retain old writes and canonical encodings.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_measurement_serialization.py tests/unit/test_compatibility_matrix.py tests/unit/test_runner_config_v57.py --cov=simulation --cov-report=term-missing -q`

Expected: all old and new accepted-set/exact-key cases pass.

## Task 10: Implement effect-complete replay and checkpoint restoration

### Intent

A replay reproduces the instrument display, not a fresh random measurement.

### Implementation Steps

1. Add `project_measurement_taken` and `project_instrument_calibrated` in `_measurement.py`; dispatch in `_replay.py`. Validate actor/item anchor, event quantity/unit, before-state equality, calibration revision progression, bounded after-state and reading identity. Reading ID must equal `"msr:" + event.request_id.value`; do not require it to equal or be derived from the separately allocated event ID. Observation provenance retains the actual event ID as direct source root.
2. Apply recorded instrument-after state only. Never read ambient/resource/route values to recompute the reading, rerun a calibration reference or sample noise.
3. Restore current instrument/reference records from v26 checkpoints through engine restore/bootstrap validation. Handle removed items and empty post-consumption record arrays explicitly.
4. Ensure physical transition fingerprints, checkpoint hashes, event exports and observation context all include the new state where selected. An instrument spec is bootstrap input, not permission to reset checkpointed condition.
5. Prove current-state replay from tick zero and suffix replay after a checkpoint agree for multiple measurements, wear, calibration, transfers and item removal.

### Required Interfaces and Contracts

Recorded display is a committed fact about an instrument interaction, not an assertion that the sampled quantity equalled it. Replay corruption must not be repaired by calculating a plausible new reading.

### Error Handling and Logging

Fail closed on missing instrument/reference, impossible before-state/revision or event/schema mismatch; safe codes only. No live-data fallback.

### Tests

Patch sampling/noise to raise during replay; it must never be called. Full/suffix fingerprint parity; calibration after a biased reference; damaged instrument transfer; combined travel/instrument selector; tampered before/after state; old replay fixtures unchanged.

### Acceptance Criteria

Live and restored physical histories have identical recorded displays, calibration state and canonical observations.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_measurement_replay.py tests/unit/test_experiment_resolution.py --cov=world --cov=simulation --cov-report=term-missing -q`

Expected: deterministic replay without sampling and all legacy experiment replay cases pass.

## Task 11: Project readings and appearances without hidden accuracy

### Intent

An agent may observe a display and be wrong about its meaning or reliability.

### Implementation Steps

1. Add `instrument: InstrumentAppearance | None = None` and `reference: ReferenceAppearance | None = None` to `ObservedItem` with frozen mutually exclusive validation. Project each only for own-held or normally visible local TOOL items with the corresponding physical sidecar. Reference appearance exposes only unit and nominal marked value so owner cognition can recognize a usable reference; physical reference value stays hidden. Do not change the underlying `Item` or legacy `ObservedItem` wire rows.
2. Actor-only occurrence public facts for `measurement_taken` contain the closed reading document; an eligible bystander sees action tag, actor and instrument/target anchors only when those anchors are independently visible, never the reading. Remote observers get no new occurrence.
3. Calibration's actor facts indicate adjustment completion, instrument/reference IDs and nominal reference mark/unit; omit raw sampled reference response, correction, residual bias/error and hidden reference value. Bystanders get action metadata only.
4. Never copy full event detail or instrument state into `public_facts`. Implement explicit allowlisted projection rather than blacklisting hidden keys.
5. Reuse committed occurrence context for restored observations; repeated `observe()` within a tick is stable and does not generate readings.
6. Preserve exact legacy resource quantity, own body temperature and item-load observations. Do not claim instruments globally obscure these pre-existing facts.

### Required Interfaces and Contracts

No new all-agent observation channel. Measurement history enters an owner's memory only from an actual actor reading or addressed testimony in Phase 4. Hidden properties must remain noninterfering except through the display or visible wear/adjustment mark.

### Error Handling and Logging

Absent instrument state means no appearance, not a manufactured default accuracy. Malformed recorded facts fail strict restore; no public traceback or data-bearing log.

### Tests

Actor/bystander/remote audience matrix; low visibility; held versus ground items; hidden inventory; paired states differing only in hidden bias/reference truth have identical appearance; reference role/nominal-mark visibility makes an ordinary calibration candidate possible; readings differ only when physically sampled; live/restored parity; old observations byte-stable; bounded facts include no truth/error/correction fields.

### Acceptance Criteria

An agent sees only a qualified display and coarse physical cues; cannot directly inspect objective reliability.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_measurement_perception.py tests/unit/test_perception_event_isolation.py --cov=world --cov=simulation --cov-report=term-missing -q`

Expected: audience isolation and noninterference pass.

## Task 12: Keep inspection and observer output read-only and redacted

### Intent

Support ordinary inspection without adding an unrelated measurement dashboard or leaking debug state into agent-visible frames.

### Implementation Steps

1. Map `measurement_taken` and `instrument_calibrated` to existing `EXPERIMENT_RESOLVED` in `observer.version.SEMANTIC_TYPE_BY_KIND`. Document this as a coarse scientific-action presentation alias; preserve actual event kind in existing metadata where already supported.
2. Audit `observer.adapt.adapt_event` for generic detail propagation; explicitly omit hidden before/after instrument state and reference truth from normal event/frame payloads. No numeric display is broadcast by the objective observer alias.
3. Keep ordinary TOOL item rendering and existing authorization gates. Agent-visible inspection may return only Task 11's observation. Objective privileged event inspection may inspect authoritative state through existing gates; it must never be fed to cognition.
4. Verify new domain-envelope decoding in existing inspection/export paths. Do not add routes, capability credentials, Godot overlays, Svelte panels or observer semantic types.

### Required Interfaces and Contracts

Observer semantic count stays 73; protocol `observer-protocol-v1`, layout, `/v1` identity and existing route counts remain unchanged. Existing clients receive valid known semantics and no instrument-private fields.

### Error Handling and Logging

Unknown/invalid event variants fail closed under existing observer behavior. Safe action/semantic names and counts only.

### Tests

Known semantic mapping for both new events; no private keys in adapted JSON; read-only adapter cannot call engine mutation; authorization matrix for objective versus agent-visible routes; existing observer replay/authority tests pass.

### Acceptance Criteria

Existing presentation clients remain compatible without a new wire surface or access to instrument truth.

### Verification

`uv run --frozen --python 3.12.14 pytest tests/unit/test_measurement_observer.py tests/unit/test_observer_replay.py tests/unit/test_observer_authority.py --cov=observer --cov=simulation --cov-report=term-missing -q`

Expected: known aliases, redaction and observer authority checks pass.

## Phase Risks and Mitigations

- Snapshot pair selection can discard earlier channels: test combined infrastructure/travel/science state, not only instrument-only runs.
- Full event details may leak through generic adapters: strict positive allowlists and serialized-payload assertions.
- Adding an appearance field can widen old schemas: conditionally version envelope 2 and preserve old bytes.

## Phase Completion Checklist

- Tasks 9–12 meet exact-key, replay and audience criteria.
- Progress remains solely in `index.md`.
