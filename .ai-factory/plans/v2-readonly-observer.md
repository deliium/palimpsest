# Implementation Plan: Read-Only Observer Architecture

Branch: main
Created: 2026-09-27
Improved: 2026-09-27 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete milestone; this plan adds a read-only presentation projection and does not claim `advanced_social_inference`, `multi_hop_testimony_tracking`, or any new capability flag.

## Compatibility contract

This plan adds a read-only observer projection that graphical clients can consume. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants intact. `WorldEngine` remains the only objective mutation authority. The observer reads detached facts and immutable `WorldEvent` records. It never receives a live `World` or `WorldState`, never calls admission, never samples `simulation.randomness`, and never writes memories, beliefs, relationships, goals, or emotions.
2. No new capability flag. No `V2CapabilityFlags` slot, no `runner-config` bump, and no Alembic revision. Unowned flags still fail closed with `capability_unimplemented`.
3. V1 regression gate stays green under flags-off and tracing-off. Catalog A–E and the reference scenario keep their current `exact_trajectory_hash` values. The observer is not an experiment arm and must not be appended to `tests/unit/test_v1_regression_gate.py`.
4. No schema bump of authoritative history. Event schemas, projector versions, and `AUTHORITATIVE_TABLES` stay unchanged. The observer protocol is a separate version, `observer-protocol-v1`.
5. No scripted emergence. Layout metadata must not add graph edges, roles, or milestone scripts. Relationship output uses the existing closed dimension codes and never friend, enemy, leader, or culture labels.
6. No LLM involvement. This plan does not call a provider and does not add a world shortcut.
7. Experiments stay reproducible. Connecting an observer, changing presentation coordinates, or seeking a historical tick must not change seeds, event ids, or `exact_trajectory_hash`.
8. Optional cognition tracing stays outside the objective fold. Observer payloads must not include cognition-trace rows, and tracing on versus off must not change the objective observer facts.

## Goal

Python simulation stays authoritative. A future Godot client is only a renderer. This plan defines the projection those clients will read. It does not implement Godot.

```text
WorldEngine
  -> immutable WorldEvents and snapshots
  -> Observer projection
  -> read-only Observer API
  -> graphical client
```

A `Location` stays a logical graph node. Screen coordinates, theme tokens, and slot positions are presentation data. They must not affect movement distance, visibility, pathfinding, action success, timing, or experiment results.

## Design Decisions (locked)

- **New bounded package.** Add `src/observer/`. Frozen dataclasses only. No Pydantic, FastAPI, SQLAlchemy, or live engine. `simulation`, `world`, `agents`, `memory`, `social`, `llm`, `persistence`, and `experiments` must not import `observer`. `api` may import `observer`.
- **Facts stay in simulation.** Add `src/simulation/observer_facts.py` with `ObjectiveScene`, a detached copy of public facts: tick, revision, locations, bodies, items, resources, weather, and agent registrations. `WorldEngine.detached_objective_facts()` returns those copies after `restore_from_snapshot` has folded events. `scene_from_facts` builds the scene. The nearest raw `WorldSnapshot` is only the replay baseline; it is not the frame when later events exist. `ReplayResult` and `DetachedObjectiveProjection` are too small for this scene. The scene contains no screen coordinates and does not import `observer`.
- **Tick cursor matches replay.** A snapshot's `next_tick` is the replay cursor: the initial checkpoint is `Tick(0)`, and the snapshot written when tick `T` commits has `next_tick == T + 1` (`TickAppendRequest`). `GET .../state?tick=T` calls `ReplayService` with that same target. `ObjectiveScene.tick` and `ObserverPlaybackCursor.tick` equal `T`. Do not subtract one. Events folded into that state are the immutable events with `event.tick < T`. Events whose `tick` is `T` have not been applied yet at cursor `T`.
- **Projection is pure.** `observer.project_frame(scene, layout) -> ObserverFrame` and `observer.adapt_event(event) -> ObserverEvent` are pure functions. They sort by stable ids. They do not call `WorldEngine`, `project_events`, or the RNG.
- **Replay, not inverse events.** Seeking to tick T calls the existing replay path: nearest snapshot at or before T, then immutable events forward through `project_events`. `scene_at_tick` copies `detached_objective_facts()` and drops the restored engine the same way `project_replay_for_inspection` does. It never calls `open_durable`. `target_tick=None` is the durable head. Do not add `AGENT_UNATE_ITEM`, `AGENT_UNDIED`, `AGENT_UNMOVED`, or any other inverse event. Previous-event navigation reconstructs an earlier tick the same way. The frame world is the state after that fold. Clients animate from `ObserverEvent` records; they do not reapply those events onto a stale snapshot.
- **Protocol version.** Constant `OBSERVER_PROTOCOL_VERSION = "observer-protocol-v1"` lives in `src/observer/version.py`. It is independent of event schema and runner-config versions. Manifests carry both the observer protocol version and the run's event schema and projector versions. Constructors and API models reject any other observer protocol version with `unsupported_observer_protocol`.
- **Ordinary view is objective.** `ObserverWorldState` includes locations, agents, items, resources, and weather. Agent records carry `agent_id`, body `entity_id`, logical `location_id`, `life_status`, inventory ids, and the objective body measures already stored on `AgentBody` (health, hunger, thirst, fatigue, temperature). They do not carry memories, beliefs, goals, emotions, utterances, private recipient ids, or relationship profiles.
- **Relationships are explicit and gated.** `ObserverRelationshipSummary` exists only for the researcher route. It lists directed pairs and the closed `RelationshipDimension` codes. Each score is the already quantized `RelationshipDimensionState.value`. A read-only persistence fetch returns dimension code and value and drops evidence before the API mapping. `InspectionService.subjective_page` stays a count page and is not this source. The ordinary frame type has no relationship field, and `project_frame` must not call the relationship projector.
- **Communication events stay structural.** `AGENT_TALKED`, `AGENT_ASKED`, and `AGENT_TOLD` carry actor, recipient, tick, sequence, and origin location. They omit utterance text, propositions, and `OccurrenceContext.private_recipient_ids`.
- **Layout is a separate document.** `LocationVisualSpec` and `ObserverLayoutCatalog` use schema `observer-layout-v1`. Store samples under `src/observer/layouts/` as package data, not as fields on `world.models.Location`. Unknown catalog location ids fail with `unknown_location_id`. A visual connection whose endpoints are not `Location.adjacent` fails with `visual_edge_not_in_graph`. A location with no spec still projects, using `Location.name` and no screen coordinates.
- **Slots are presentation-only.** Inside one location, bodies are ordered by `entity_id` string. `slot_index` is that rank. When the spec has `slot_anchors`, index `i` uses anchor `i` while anchors remain. Further occupants use a fixed golden-angle offset inside `visual_bounds` when bounds exist: angle radians = `slot_index * 2.399963`, radius scaled by `min(width, height) * 0.25`. When `visual_bounds` is absent, `local_x` and `local_y` stay empty and only `slot_index` is set. No `random` module and no `simulation.randomness`. Recomputing slots must not write simulation state.
- **Ordering.** Client-visible order is `(tick, sequence)`, matching `WorldEvent`. HTTP pages use an exclusive cursor, the same rule as `EventKeysetCursor`. Tick-range responses are ordered by tick.
- **Routes stay on `/v1`.** Do not add `/v2` simulation routes. Capability for ordinary observer HTTP and WebSocket is `objective_inspection`. The relationship route uses `subjective_debug` and fails with `debug_disabled` when debug is off. Credentials stay in the capability header or WebSocket subprotocol, never the query string.
- **Client messages cannot mutate.** The WebSocket is server-push. A client text frame is ignored and answered with a `rejected` envelope reason `client_mutation_rejected`. It must not reach `WorldEngine`.
- **Sources share one shape.** `LiveObserverSource` and `ReplayObserverSource` are Python protocols in `src/observer/sources.py`. Both return `ObserverManifest`, `ObserverFrame`, and `ObserverEvent`. They are the client-facing abstraction. This plan does not implement a Godot client.
- **Logging.** Domain modules use stdlib loggers. API routes use `infrastructure.logging.get_logger`. DEBUG may include ids, ticks, sequence numbers, counts, protocol version, and reason codes. INFO is route and session summaries. No coordinates at INFO, no utterance text, no seeds, no credentials, no belief or relationship scores in API access logs.

## Non-Goals

- Implementing Godot, sprite animation, pixel movement, cameras, or input that selects actions
- Converting locations into a grid or cell world
- Adding fields to `Location`, `WorldEvent`, `WorldState`, or runner JSON
- Inverse events or mutating history backwards
- Putting presentation coordinates into pathfinding, visibility, movement cost, or experiment metrics
- Exposing memories, beliefs, goals, emotions, or utterances on ordinary objective routes
- A new capability flag, Alembic migration, or V1 regression-gate experiment

## Observer contracts

All domain contracts are frozen dataclasses in `src/observer/contracts.py`, exported from `src/observer/__init__.py`. API copies in `src/api/observer_schemas.py` are `StrictModel` (`extra=forbid`) and must not add fields the domain types lack.

`ObserverManifest`

- `protocol_version` (`observer-protocol-v1`)
- `layout_schema_version` (`observer-layout-v1`)
- `layout_id` and `layout_hash`
- `ordering` literal `tick_sequence`
- `read_only` literal true
- `event_types` closed tuple of semantic types below
- run `event_schema_version` and `projector_version` copied from the manifest, not invented

`ObserverPlaybackCursor`

- `run_id`, `mode` (`live` or `replay`), `tick`, `sequence` (null when the tick has no events)
- `protocol_version`
- exclusive resume pair `after_tick`, `after_sequence`

`ObserverFrame`

- `protocol_version`, `cursor`, `world` (`ObserverWorldState`)
- optional `events` for a delta frame, already ordered

`ObserverWorldState`

- `tick`, `revision`
- ordered `locations`, `agents`, `items`, `resources`, `weather`
- no relationship, memory, belief, goal, emotion, or utterance field

`ObserverLocation`

- `location_id`, domain `name`, presentation `display_name`
- ordered neighbor ids copied from `Location.adjacent` (simulation graph, not visual edges)
- optional presentation block: `screen_position`, `visual_bounds`, `theme`, `icon_ref`, `background_ref`, connection anchors
- presentation block is absent when the catalog has no spec for that id

`ObserverAgent`

- `agent_id`, `entity_id`, `location_id`, `life_status`, ordered inventory ids
- objective body measures
- optional `presentation_slot` (`slot_index`, `local_x`, `local_y`)

`ObserverItem`, `ObserverResource`, `ObserverWeather`

- stable ids, domain names and kinds, `location_id` or `holder_id` exactly as the objective models already store them
- resource quantity and unit copied, not recomputed
- weather `condition` only; do not derive ambient temperature in the observer

`ObserverEvent`

- `protocol_version`, semantic `type`, `domain_kind`, `event_id`, `tick`, `sequence`
- optional `actor_id`, `target_id`, `item_id`, `resource_id`, `origin_location_id`, `destination_location_id`
- construction rejects attribute names `pixels`, `sprite`, `animation`, `dx`, `dy`, and any type prefix `AGENT_UN`

Closed semantic types, one per existing `EventDetails.kind`:

| `domain_kind` | semantic `type` |
| --- | --- |
| `move` | `AGENT_MOVED` |
| `search` | `AGENT_SEARCHED` |
| `take` | `AGENT_TOOK_ITEM` |
| `drop` | `AGENT_DROPPED_ITEM` |
| `give` | `AGENT_GAVE_ITEM` |
| `eat` | `AGENT_ATE_ITEM` |
| `drink` | `AGENT_DRANK` |
| `sleep` | `AGENT_SLEPT` |
| `talk` | `AGENT_TALKED` |
| `ask` | `AGENT_ASKED` |
| `tell` | `AGENT_TOLD` |
| `help` | `AGENT_HELPED` |
| `attack` | `AGENT_ATTACKED` |
| `flee` | `AGENT_FLED` |
| `wait` | `AGENT_WAITED` |
| `weather_changed` | `WEATHER_CHANGED` |
| `resource_regenerated` | `RESOURCE_REGENERATED` |
| `needs_applied` | `NEEDS_APPLIED` |
| `exposure_applied` | `EXPOSURE_APPLIED` |
| `died` | `AGENT_DIED` |

`AGENT_GAVE_ITEM` maps `Given.recipient_id` to `target_id`, `Given.item_id` to `item_id`, and `OccurrenceContext.origin_location_id` to `origin_location_id`. No other fields.

`ObserverRelationshipSummary` (researcher route only)

- `owner_id`, `target_id`
- ordered dimension records using existing codes (`trust`, `fear`, `affection`, `debt`, `respect`, `resentment`, `familiarity`, `dependency`)
- each record is `dimension` plus the stored `RelationshipDimensionState.value`
- no evidence items and no signal kinds

`LocationVisualSpec`

- `location_id`, `display_name`, `screen_position`, `visual_bounds`, `theme`, `icon_ref`, `background_ref`
- `connection_anchors` keyed only by neighbor location ids
- ordered `slot_anchors`

## HTTP and WebSocket

All HTTP methods are `GET`. Register the router from `src/api/app.py` beside the existing `/v1` routers. Use the same error helpers as inspection (`bad_request`, not-found, forbidden) and the same capability dependencies.

| Method | Path | Capability | Response |
| --- | --- | --- | --- |
| GET | `/v1/simulations/{run_id}/observer/manifest` | `objective_inspection` | `ObserverManifest` |
| GET | `/v1/simulations/{run_id}/observer/state` | `objective_inspection` | current `ObserverFrame` |
| GET | `/v1/simulations/{run_id}/observer/state?tick=` | `objective_inspection` | frame reconstructed at that tick |
| GET | `/v1/simulations/{run_id}/observer/events` | `objective_inspection` | ordered `ObserverEvent` page |
| GET | `/v1/simulations/{run_id}/observer/ticks` | `objective_inspection` | tick summaries between `from_tick` and `to_tick` |
| GET | `/v1/simulations/{run_id}/observer/events/{event_id}` | `objective_inspection` | one `ObserverEvent` |
| GET | `/v1/simulations/{run_id}/observer/run` | `objective_inspection` | non-secret run metadata |
| GET | `/v1/simulations/{run_id}/observer/agents/{agent_id}/relationships` | `subjective_debug` | `ObserverRelationshipSummary` page |
| WS | `/v1/simulations/{run_id}/observer/stream` | `objective_inspection` | live envelopes |

Event query parameters match inspection: optional `after_tick` and `after_sequence` together, or neither; `limit` bounded by `api_max_page_size`. Incomplete cursors return `incomplete_event_cursor`. Optional `layout_id` selects the presentation catalog and defaults to `reference-v1`.

Event pages are adapted from full `WorldEvent` rows returned by `ReplayService.read_event_page`. `EventSummaryOut` stays the thin inspection summary.

Run metadata includes `run_id`, `world_id`, availability, protocol version, event schema version, projector version, current tick, and latest `(tick, sequence)`. It omits seed, credentials, LLM settings, experiment condition values, and cognition traces.

WebSocket query may carry `after_tick` and `after_sequence` only. The live tail polls the ordered event journal on `(tick, sequence)`. It does not subscribe to `StreamFanout` or decode that socket's base64 outbox envelopes. A slow subscriber disconnects with the same non-blocking behavior as `SlowConsumerError` in `src/api/streaming.py`, so the queue never waits inside tick commit. First server envelope is `hello` with manifest, current frame, and cursor. Following envelopes are `event` in `(tick, sequence)` order, then `tick` when the high-water moves, and `heartbeat` with the cursor. `completion` ends the session the same way the existing stream ends. A cursor ahead of the high-water closes the socket the way `cursor_ahead_of_high_water` already fails HTTP. A reconnecting client that missed events loads `GET .../observer/events` for the exclusive gap, then resumes the socket at the last applied cursor. The server does not depend on the client to mutate history.

Envelope `kind` is a closed set: `hello`, `event`, `tick`, `heartbeat`, `rejected`, `completion`.

## Commit Plan

- **Commit 1** (after tasks 1–3): `feat(observer): add versioned read-only presentation contracts`
- **Commit 2** (after tasks 4–6): `feat(observer): project objective frames from committed events`
- **Commit 3** (after tasks 7–9): `feat(api): serve read-only observer history and live stream`
- **Commit 4** (after tasks 10–12): `test(observer): keep presentation out of simulation authority`

Each checkpoint is a git commit on `main` created when those tasks are done. Do not squash them into one commit at the end.

## Tasks

### Phase 1: Contracts, Layout, and Boundaries

- [x] Task 1: Add versioned observer contracts.
  - Deliverable: frozen types listed under Observer contracts, plus `OBSERVER_PROTOCOL_VERSION` and `OBSERVER_LAYOUT_SCHEMA_VERSION`. Constructors reject a foreign protocol version, a non-boolean `read_only` other than true, duplicate ids, unordered inventories that arrive as a set, an inverse type name, and any extra presentation instruction field (`pixels`, `sprite`, `animation`, `dx`, `dy`) with reason code `presentation_instruction_forbidden` or `unsupported_observer_protocol`. `ObserverWorldState` has no relationship attribute. Semantic event types are exactly the closed table.
  - Logging: logger `observer.contracts`. DEBUG on successful construction with `protocol_version`, object kind, and id count. ERROR with field name and reason code on validation failure. No body measures and no scores at INFO.
  - Files: `src/observer/version.py`, `src/observer/contracts.py`, `src/observer/__init__.py`, `tests/unit/test_observer_contracts.py`.

- [x] Task 2: Add presentation layout and deterministic slots.
  - Deliverable: `LocationVisualSpec` and `ObserverLayoutCatalog` (`observer-layout-v1`) in `src/observer/layout.py`. Load JSON from `src/observer/layouts/` by catalog id. Fail closed on unknown location ids referenced by the catalog (`unknown_location_id`) and on connection anchors that are not in that location's `adjacent` tuple (`visual_edge_not_in_graph`). Missing spec for a scene location is allowed. `assign_slots(location_id, occupant_entity_ids, spec)` returns slot indexes in `entity_id` sort order. Anchor `i` fills index `i` while anchors remain. Further occupants use the golden-angle offset only when `visual_bounds` is present. When bounds are absent, `slot_index` is still set and `local_x` and `local_y` stay empty. The same occupants and spec always return the same coordinates. `world.models.Location` gains no field.
  - Logging: logger `observer.layout`. DEBUG `layout_loaded catalog_id=%s location_count=%s schema=%s`. WARNING on a scene location with no spec, reason code `layout_spec_missing`, location id only. ERROR on `unknown_location_id` and `visual_edge_not_in_graph`. Do not log coordinates at INFO.
  - Files: `src/observer/layout.py`, `src/observer/layouts/reference-v1.json` (presentation metadata for the canonical reference locations only), `tests/unit/test_observer_layout.py`.

- [x] Task 3: Enforce the import boundary.
  - Deliverable: register the package in `pyproject.toml` beside the existing entries: `[tool.uv] packages`, `[tool.hatch.build.targets.wheel] packages` (`src/observer`), and `[tool.importlinter] root_packages` (`observer`). The layout JSON under `src/observer/layouts/` ships as package data. Extend import-linter contracts so `observer` is forbidden from `fastapi`, `starlette`, `uvicorn`, `pydantic`, `pydantic_core`, `sqlalchemy`, `alembic`, `asyncpg`, `persistence`, `api`, `infrastructure`, `simulation.engine`, `simulation.randomness`, `world._state`, `world._operations`, `world._rules`, `world._replay`, `world._perception`, and `world._physical`. Add `observer` to the forbidden lists of `world`, `simulation`, `agents`, `memory`, `social`, and `experiments`. Add `observer` to the domain sets that already forbid FastAPI, SQLAlchemy, and Pydantic. `api` is allowed to import `observer`. An architecture test fails if `src/observer` imports those modules, if `src/simulation/engine.py` or `src/world` mentions `LocationVisualSpec`, or if `project_frame` is referenced from `simulation.engine`.
  - Logging: no production logger. The architecture test asserts the contract ids exist and that `observer.contracts` does not import `simulation.randomness`.
  - Depends on tasks 1 and 2.
  - Files: `pyproject.toml`, `tests/architecture/test_observer_isolation.py`.
<!-- Commit checkpoint: tasks 1-3 -->

### Phase 2: Objective Projection

- [x] Task 4: Assemble a detached objective scene.
  - Deliverable: `ObjectiveScene` in `src/simulation/observer_facts.py`. Add `WorldEngine.detached_objective_facts()` that returns copied locations, bodies, items, resources, weather, registrations, tick, and revision after events have been folded. `scene_from_facts` builds `ObjectiveScene` from that copy. `scene_from_snapshot` remains only for a snapshot whose `next_tick` is already the requested cursor and whose event list is empty. Set `tick` from the restored engine cursor, which matches `snapshot.next_tick` when no later events are folded, including `Tick(0)` for the initial checkpoint. Do not copy seed into a field the observer frame can see. Do not import `observer`. The new engine method only reads; it does not commit a tick or replace `WorldState`.
  - Logging: logger `simulation.observer_facts`. DEBUG `objective_scene_built run_id=%s tick=%s location_count=%s body_count=%s item_count=%s`. ERROR `objective_scene_rejected reason_code=%s` for an empty world id or a snapshot whose weather is not defined for every location (the snapshot type already guarantees this; surface the existing validation error). No seed.
  - Depends on task 1.
  - Files: `src/simulation/observer_facts.py`, `src/simulation/engine.py`, `src/simulation/__init__.py`, `tests/unit/test_observer_facts.py`.

- [x] Task 5: Adapt domain events into semantic observer events.
  - Deliverable: `adapt_event(event: WorldEvent) -> ObserverEvent` in `src/observer/adapt.py` implementing the closed table. `domain_kind` is the `EventDetails.kind` literal, including `weather_changed`, `resource_regenerated`, `needs_applied`, and `exposure_applied`. Preserve `event_id`, `tick`, and `sequence`. Map give, take, drop, eat, and drink item ids; move and flee destination ids onto `destination_location_id`; weather and origin locations onto `origin_location_id`. Talk, ask, and tell omit utterance content and private recipient ids. Unknown detail types raise `TypeError` with reason code `unknown_event_kind`. The adapter source must not contain `AGENT_UN`, `pixels`, or `play animation`.
  - Required assertions in `tests/unit/test_observer_adapter.py`: a `Given` event becomes `AGENT_GAVE_ITEM` with actor, target, item, and origin location; a `WeatherChanged` event has `domain_kind=weather_changed` and semantic type `WEATHER_CHANGED`; a `ResourceRegenerated` event has `domain_kind=resource_regenerated` and semantic type `RESOURCE_REGENERATED`; a page of mixed events stays in input order; a `Talked` event JSON has no utterance string; constructing an event whose type is `AGENT_UNDIED` raises.
  - Logging: logger `observer.adapt`. DEBUG `observer_event_adapted event_id=%s tick=%s sequence=%s domain_kind=%s semantic_type=%s`. ERROR on unknown kind with the event id and reason code. No utterance text.
  - Depends on task 1.
  - Files: `src/observer/adapt.py`, `src/observer/__init__.py`, `tests/unit/test_observer_adapter.py`.

- [x] Task 6: Project an objective frame.
  - Deliverable: `project_frame(scene, layout, *, mode) -> ObserverFrame` in `src/observer/project.py`. Locations keep domain adjacency. Display names and screen geometry come only from the catalog. Agents are joined through registrations; a body with no registration is projected as an objective body with null `agent_id` and reason code logged `unregistered_body`. Slots come from task 2. Items, resources, and weather copy objective fields. `mode` is `live` or `replay` and is stored on the cursor. The function signature must not accept `World`, `WorldState`, or `WorldEngine`. Changing the catalog must not change any objective field of the frame (ids, life status, quantities, neighbor ids).
  - Logging: logger `observer.project`. DEBUG `observer_frame_projected run_id=%s tick=%s mode=%s agent_count=%s location_count=%s`. WARNING `unregistered_body` with entity id. INFO not used for individual coordinates.
  - Depends on tasks 2, 4, and 5.
  - Files: `src/observer/project.py`, `tests/unit/test_observer_projection.py`.
<!-- Commit checkpoint: tasks 4-6 -->

### Phase 3: History, Sources, and API

- [x] Task 7: Reconstruct historical frames by replay and share source protocols.
  - Deliverable: `ReplayObserverSource` and `LiveObserverSource` in `src/observer/sources.py`. Both expose `manifest()`, `frame()`, and `events_after(after_tick, after_sequence, limit)`. `ReplayObserverSource` holds an `ObjectiveScene` built from `detached_objective_facts()` after the fold, plus the immutable events `ReplayService` applied. It does not call the engine. `LiveObserverSource` holds the latest committed scene and events supplied by the caller. `src/api/observer_service.py` loads history through `scene_at_tick`: call `ReplayService.replay`, copy facts, drop the engine, and never call `open_durable`. Current state uses `target_tick=None` (durable head). A requested tick uses that target. Seeking to a previous tick builds a new frame from a fresh replay. It does not apply inverse events and does not append events. A tick beyond the run high-water returns the existing replay unreachable status, not a mutated clock.
  - Required test: two reconstructions of the same tick produce equal objective frames. When the nearest snapshot `next_tick` is behind the target, the scene locations differ from that raw snapshot and match a second fold of the same events. The event ids in the reconstructed range equal the committed event ids in order. The source protocol methods return the same dataclass types for live and replay. The service return value has no `WorldEngine` attribute.
  - Logging: logger `api.observer` inside the service, because the service is API composition. DEBUG `observer_replay_loaded run_id=%s target_tick=%s snapshot_next_tick=%s event_count=%s`. ERROR `observer_replay_failed reason_code=%s`. The observer package sources log DEBUG `observer_source_frame mode=%s tick=%s` on logger `observer.sources`.
  - Depends on tasks 4, 5, and 6.
  - Files: `src/observer/sources.py`, `src/simulation/replay.py`, `src/api/observer_service.py`, `tests/unit/test_observer_replay.py`.

- [x] Task 8: Add read-only HTTP observer routes.
  - Deliverable: the GET routes in the HTTP table, Pydantic models in `src/api/observer_schemas.py`, and router inclusion in `src/api/app.py`. No POST, PUT, PATCH, or DELETE. Page limits use `settings.api_max_page_size`. Optional query `layout_id` defaults to `reference-v1` and is loaded by the API catalog loader. State without `tick` uses `scene_at_tick` with `target_tick=None`. State with `tick` uses task 7. Event pages call `ReplayService.read_event_page` and `adapt_event` on each full `WorldEvent`. They do not map `EventSummaryOut`. Event detail by `event_id` is a single adapted event or a not-found code `observer_event_not_found`. Run metadata omits seed and credentials. Route functions do not call `WorldEngine` methods that advance a tick.
  - Logging: logger `api.routes.observer`. INFO one line per request with route template, status, `run_id`, duration, and result count or tick, matching `src/api/routes/inspection.py`. DEBUG cursor values. ERROR only through the existing API error path with reason codes. No frame payloads at INFO.
  - Depends on task 7.
  - Files: `src/api/routes/observer.py`, `src/api/observer_schemas.py`, `src/api/observer_service.py`, `src/api/app.py`, `tests/unit/test_observer_api.py`.

- [x] Task 9: Add the live observer WebSocket and reconnect gap.
  - Deliverable: `WS /v1/simulations/{run_id}/observer/stream` in `src/api/routes/observer_stream.py`. Auth matches `src/api/routes/streams.py` (`objective_inspection`, subprotocol `palimpsest.v1`, no query-string credential). Resume query is exclusive `(after_tick, after_sequence)`. Poll the same ordered event journal as the HTTP event range. Do not subscribe to `StreamFanout` and do not decode its base64 outbox payloads. A full subscriber queue disconnects the client and does not block tick commit, matching `SlowConsumerError` in `src/api/streaming.py`. The first payload is `hello`. Later payloads are ordered `event` envelopes, `tick` when the high-water advances, `heartbeat` on the existing heartbeat interval, and `completion`. A client message produces `rejected` with `client_mutation_rejected` and does not change the run. Reconnect recovery is: HTTP event page returns every event strictly after the saved cursor and through the server high-water, in order, with no duplicates; the next socket session starts after the last event the client applied.
  - Logging: logger `api.routes.observer_stream`. INFO `observer_stream_open` and `observer_stream_disconnect` with `run_id` and cursor. WARNING `observer_stream_rejected reason_code=client_mutation_rejected`. DEBUG `observer_stream_gap` with from-cursor, to-cursor, and event count. No event payloads.
  - Depends on tasks 5 and 8.
  - Files: `src/api/routes/observer_stream.py`, `src/api/app.py`, `tests/unit/test_observer_stream.py`.
<!-- Commit checkpoint: tasks 7-9 -->

### Phase 4: Privacy, Authority Proofs, and Docs

- [x] Task 10: Add the researcher relationship endpoint without objective leakage.
  - Deliverable: `GET /v1/simulations/{run_id}/observer/agents/{agent_id}/relationships` requires `subjective_debug`. When debug is disabled, respond `debug_disabled`. Add a read-only method on the subjective persistence reader that returns, for one owner, each target id with dimension code and `RelationshipDimensionState.value`. Drop evidence items before the value leaves persistence. Map that tuple through `project_relationship_summaries` in `src/observer/relationships.py`. Do not read `InspectionService.subjective_page` or `load_relationships_page` for scores. Output is `ObserverRelationshipSummary` only. `project_frame` does not import or call that function. Ordinary manifest, state, event, tick, run, and stream schemas have no relationship, memory, belief, goal, emotion, or utterance field. Dimension codes stay the existing eight. Copy the stored value; do not quantize it a second time.
  - Logging: logger `observer.relationships` DEBUG `relationship_summary_projected owner_id=%s target_count=%s`. Do not log scores. API INFO `route_observer_relationships` with `run_id`, status, and count only.
  - Depends on tasks 6 and 8.
  - Files: `src/observer/relationships.py`, `src/persistence/subjective_sqlalchemy.py`, `src/api/routes/observer.py`, `src/api/observer_service.py`, `tests/unit/test_observer_privacy.py`.

- [x] Task 11: Prove the observer cannot change simulation results.
  - Deliverable: `tests/unit/test_observer_authority.py` covers every proof below, using the existing reference scenario or a smaller deterministic runner fixture already used by engine tests.
    - After `project_frame` and after each GET observer route, the committed event ids and the objective state hash equal the hashes taken before the call.
    - Two runs with the same seed and config, one with observer projection invoked after every tick and one without, have equal `exact_trajectory_hash` and equal event sequences.
    - Two layout catalogs with different `screen_position` values produce equal objective neighbor lists, life statuses, item holders, and action outcomes, and unequal presentation coordinates.
    - Historical observer state at tick T matches a second replay to T on objective fields. When events sit after the nearest snapshot, those objective locations differ from the raw snapshot and match the folded facts.
    - Adapted events preserve `(tick, sequence)` order of the source `WorldEvent` tuple, including gaps in sequence only when the source itself has those sequences.
    - A client that stops at cursor C and then calls the event range receives exactly the missed events, and a following stream session does not repeat them.
    - Ordinary state, event detail, and stream `hello` JSON do not contain keys `relationship`, `memory`, `belief`, `goal`, `emotion`, `utterance`, or `private_recipient`. The relationship route is absent from responses unless the debug capability is presented.
    - `src/observer` does not reference `WorldEngine` method names that commit ticks (`step`, `commit`, `submit`).
  - Logging: tests assert the DEBUG tokens from tasks 5, 6, and 9. No new production logger.
  - Depends on tasks 7, 8, 9, and 10.
  - Files: `tests/unit/test_observer_authority.py`, `tests/architecture/test_observer_isolation.py`.

- [x] Task 12: Document the read-only observer contract.
  - Deliverable: mandatory docs checkpoint through `/aif-docs`. Add `docs/observer.md` describing the authority split, the protocol version, the route table, live versus replay sources, replay seek, reconnect, layout isolation, and the objective versus researcher privacy split. Link it from `docs/architecture.md` and `docs/research-api.md`. State that Godot is a future client and is not in this repository. State that presentation coordinates are not simulation coordinates. Do not document inverse events.
  - Logging: none in docs. Implementation logs stay metadata-only as specified above.
  - Depends on tasks 8, 9, 10, and 11.
  - Files: `docs/observer.md`, `docs/architecture.md`, `docs/research-api.md`.
<!-- Commit checkpoint: tasks 10-12 -->
