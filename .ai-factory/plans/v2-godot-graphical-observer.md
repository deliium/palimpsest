# Implementation Plan: Godot Graphical Observer

Branch: main
Created: 2026-09-27
Improved: 2026-09-27 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete milestone; this plan adds a read-only Godot renderer and does not claim `advanced_social_inference`, `multi_hop_testimony_tracking`, or any new capability flag.

## Compatibility contract

This plan adds a presentation client. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants stay intact. `WorldEngine` remains the only objective mutation authority. The client reads observer HTTP GET routes and the observer WebSocket. It never calls simulation control or any other mutating route.
2. No new capability flag. No `V2CapabilityFlags` slot, no `runner-config` bump, and no Alembic revision.
3. V1 regression gate stays green under flags-off and tracing-off. The client is not an experiment arm and must not be appended to `tests/unit/test_v1_regression_gate.py`.
4. No schema bump of authoritative history and no change to `observer-protocol-v1` or `observer-layout-v1`.
5. No scripted emergence. Visual zones, colors, and animation do not add graph edges, roles, or milestone scripts.
6. No LLM involvement.
7. Experiments stay reproducible. Connecting the client, moving the camera, or changing playback speed must not change seeds, event ids, or `exact_trajectory_hash`.
8. Optional cognition tracing stays outside the client. Do not request cognition-trace rows, memories, beliefs, goals, emotions, or utterance text.

## Goal

A researcher can watch a running V2 world in a Godot 4.7 2D client. The client lives in this repository as a separate presentation module. Python simulation code does not import it and does not depend on it.

```text
FastAPI Observer API
  -> HTTP GET + WebSocket
  -> Godot Observer
  -> 2D graphical presentation
```

Locations stay logical graph nodes. Screen positions, zone shapes, connection drawings, and agent slots are presentation. They are never written back to the simulation.

The existing reference catalog draws Camp, Spring, Grove, and Ridge (`src/observer/layouts/reference-v1.json`). Names such as Village, Forest, River, Cave, Storage, and Abandoned House are the same kind of visual zone when a frame includes them. This plan does not add those names to the simulation.

## Design Decisions (locked)

- **Client root.** `clients/godot-observer/`. Godot 4.7 project (`config/features` includes `4.7` and `GL Compatibility`). Reference editor and export binary: Godot 4.7.2 stable. Language: GDScript. Dimension: 2D. Renderer: Compatibility (`gl_compatibility` on desktop and mobile keys).
- **Web export is the deployment target.** Commit a Web export preset with thread support off. Use `HTTPRequest` and `WebSocketPeer` only. Do not use `Thread`, GDExtension, C#, `.csproj`, native sockets, or any native-only plugin. `JavaScriptBridge` is allowed only behind `OS.has_feature("web")`.
- **Python boundary.** Do not add the client to Hatch, uv, or import-linter packages. Do not import it from `src/`. Do not mount it from FastAPI. Same-origin hosting is a reverse-proxy concern, not an API dependency.
- **Protocol consumption.** Accept `observer-protocol-v1` only. A different `protocol_version` shows an error and does not apply the frame. Do not extend the Python observer package.
- **Read-only transport.** Allowed HTTP methods are GET:
  - `/v1/simulations/{run_id}/observer/manifest`
  - `/v1/simulations/{run_id}/observer/state`
  - `/v1/simulations/{run_id}/observer/events`
  - `/v1/simulations/{run_id}/observer/run`
  Optional event reads may include `/v1/simulations/{run_id}/observer/events/{event_id}` and `/v1/simulations/{run_id}/observer/ticks`. The relationship route is out of scope. The client never sends a WebSocket text or binary payload. The server answers client frames with `rejected` / `client_mutation_rejected`.
- **Credentials.** HTTP header `x-palimpsest-token`. WebSocket subprotocols `palimpsest.v1` and `palimpsest.token.<token>`, which is the path that works in browser WebSocket exports. Never put the token in the query string. Never commit a token. A gitignored local override may hold it. Logs never include the token.
- **Origin.** Core URL code accepts an origin string and joins paths. On Web export, the origin is `window.location.origin` via `JavaScriptBridge`. Off Web, the origin is the project setting `palimpsest/observer_origin`, default empty. Empty origin shows `observer_origin_missing`. Scripts under `clients/godot-observer/scripts/` must not contain `localhost` or `127.0.0.1`.
- **Logical state versus animation.** The committed event is already resolved. The client updates its logical model immediately, then plays a visual tween. Tweens never delay socket reads, HTTP refresh, or the next tick. Playback speed is a client-only multiplier. At speed 1, motion lasts about 0.6 seconds. Higher speed shortens the tween. At speed 8 or when more than three visual motions are pending, snap to the logical pose and skip intermediate frames. The client never posts a tick rate.
- **Folded history stays in the frame.** `LiveObserverSource.frame()` includes every event already folded into `world`. `hello.frame.events` and a state response’s `events` array are that history. Render `world` and the cursor from them. Do not enqueue those events as tweens and do not append them to the live event log. Tweens and new log lines come only from `kind=event` envelopes and from gap-fill pages.
- **Resume cursor.** `world.tick` is the replay head. The resume pair is `cursor.after_tick` and `cursor.after_sequence`, or the last applied event. Either field null, or `after_sequence < 0`, means omit both query parameters. HTTP rejects `after_sequence < 0` (`ge=0`). The socket closes with `4400` for a negative sequence and with `4409` when `after_tick >= world.tick`. Send the pair only when both values are `>= 0`. The events page is `{count, events, limit}` with no next link. Page with the last event’s `(tick, sequence)` until `events.size() < limit`.
- **Frames carry quantities.** `ObserverEvent` does not include health, hunger, thirst, fatigue, temperature, resource quantity, or utterance text. On each `tick` envelope, and after the gap-fill page on reconnect, the client GET-refreshes `observer/state` without waiting for tweens. That refresh replaces agents, items, resources, weather, and measures. It does not enqueue `frame.events`. Live envelopes start the animation.
- **Layout space.** `visual_bounds`, `connection_anchors`, `slot_anchors`, and `presentation_slot.local_x` / `local_y` are positions in one layout space, the same space as `screen_position`. Do not add `screen_position` to those values. Godot 2D positive Y points down, which matches `reference-v1` (Spring is at negative Y). Do not negate Y. Multiply by `pixels_per_unit` only.
- **Slots.** Use `presentation_slot.local_x` and `local_y` when both are present, as layout coordinates. If the slot has no coordinates, display a fallback with the same rule as `observer.layout.assign_slots`: occupants ordered by `entity_id`, golden angle `2.399963`, radius `min(width, height) * 0.25` from the bounds center when `visual_bounds` exist. That fallback is display-only. The client never sends slot indexes or coordinates.
- **Missing layout geometry.** If a location has no `screen_position` and no `visual_bounds`, place it for display on a ring ordered by `location_id` and log `layout_position_missing`. Connections are drawn only for ids in `neighbor_ids`. Prefer `connection_anchors` when present; otherwise a straight segment between zone centers. `connection_anchors` on the wire is a list of `[neighbor_id, {x, y}]` pairs, not the catalog’s dict.
- **Scale.** Layout numbers in `reference-v1` are small. One presentation constant, `pixels_per_unit` default 8, converts them to pixels. That constant is not a simulation distance.
- **Affected body.** Match tokens by `entity_id`. `agent_id` is the registration label. For `AGENT_DIED`, `NEEDS_APPLIED`, and `EXPOSURE_APPLIED`, the body is `target_id` (`adapt_event` copies `body_id` there) and `actor_id` may be null. For the other semantic types the acting body is `actor_id`.
- **Visual language.** Placeholder shapes and theme colors. No final art. Stable color from a deterministic hash of `agent_id`, or `entity_id` when `agent_id` is null. Label with `agent_id` or else `entity_id`. `life_status` `dead` is a distinct marker; other values stay unmarked as dead.
- **Body measures in the inspector.** Show health, hunger, thirst, fatigue, and temperature when `measures` is present on the agent record. Today's objective frames include those fields for `objective_inspection`. If a payload omits `measures`, hide those rows. Do not call `subjective_debug` to obtain them.
- **Speech.** `AGENT_TALKED`, `AGENT_ASKED`, and `AGENT_TOLD` show a short bubble with the semantic label and the other agent id. They do not invent dialogue. The bubble expires quickly (about 2 seconds at speed 1, shorter when sped up, skipped when motion is skipped). The event log keeps the structural line.
- **Unknown events.** A semantic `type` outside the closed server list is appended to the event log and does not throw. Closed types all have a visual or activity response.
- **Logging.** GDScript logger in `scripts/log.gd`. Format: `[observer.<area>] message key=value`. Levels DEBUG, INFO, WARN, ERROR. Project setting `palimpsest/log_level` defaults to `DEBUG` and can be set to `WARN` for a web export without code edits. DEBUG may include run id, tick, sequence, event id, semantic type, and reason codes. INFO is session open, close, and bootstrap complete. No tokens, seeds, coordinates at INFO, utterance text, or relationship scores.

## Semantic visuals

Use the protocol type, not the informal alias.

| Informal request | Protocol `type` | Visual |
| --- | --- | --- |
| move | `AGENT_MOVED` | Token travels along the rendered connection from origin to destination |
| resource found | none; use `AGENT_SEARCHED` and `RESOURCE_REGENERATED` | Search pulse on the actor's zone; resource marker pulse. A literal `RESOURCE_FOUND` is unknown and only logged |
| item taken | `AGENT_TOOK_ITEM` | Ground marker moves toward the actor |
| item dropped | `AGENT_DROPPED_ITEM` | Marker moves from the actor into the zone |
| item given | `AGENT_GAVE_ITEM` | Marker moves from actor toward target |
| ate | `AGENT_ATE_ITEM` | Short consume mark on the actor |
| drank | `AGENT_DRANK` | Short drink mark on the actor |
| slept | `AGENT_SLEPT` | Rest mark on the actor |
| attacked | `AGENT_ATTACKED` | Strike mark between actor and target |
| fled | `AGENT_FLED` | Same path motion as `AGENT_MOVED` when a destination is present |
| helped | `AGENT_HELPED` | Link mark between actor and target |
| died | `AGENT_DIED` | Body on `target_id` switches to the dead marker |
| talked | `AGENT_TALKED` | Speech bubble |
| asked / told | `AGENT_ASKED`, `AGENT_TOLD` | Speech bubble, same lifetime rules |
| weather | `WEATHER_CHANGED` | Pulse the origin zone; the frame refresh sets the condition tint |
| waited | `AGENT_WAITED` | Activity label only |
| needs / exposure | `NEEDS_APPLIED`, `EXPOSURE_APPLIED` | Activity label on the body in `target_id`; measures come from the frame refresh |

## Non-Goals

- Changing `src/observer`, the observer routes, or event schemas
- Calling simulation mutation APIs or sending WebSocket payloads
- A grid or cell simulation
- Final character art, tilemaps, or lighting
- Memory, theory of mind, cognition, belief, goal, or relationship inspectors
- Fetching or displaying utterance text
- Serving the web export from the FastAPI app
- A Godot binary dependency in default pytest

## Commit Plan

- **Commit 1** (after tasks 1–4): `feat(godot): add a read-only observer client shell`
- **Commit 2** (after tasks 5–8): `feat(godot): bootstrap live sessions and draw location zones`
- **Commit 3** (after tasks 9–12): `feat(godot): present agents and animate observer events`
- **Commit 4** (after tasks 13–16): `feat(godot): inspect agents and smoke-test fixture playback`

Each checkpoint is a git commit on `main` created when those tasks are done. Do not squash them into one commit at the end. `git.create_branches` is false, so implementation stays on the current branch.

## Tasks

### Phase 1: Isolated Project Shell

- [x] Task 1: Create the Godot 4.7 client shell.
  - Deliverable: `clients/godot-observer/` opens in Godot 4.7.2 as a 2D Compatibility project named Palimpsest Observer. `project.godot` sets `config/features` to `4.7` and `GL Compatibility`, `renderer/rendering_method` and the mobile override to `gl_compatibility`, and main scene `res://scenes/main.tscn`. No C# section, no `addons/` with native binaries, and no GDExtension. Commit `export_presets.cfg` for a Web preset with threads disabled. Placeholder main scene shows a loading label. Add `scripts/log.gd` with the level gate from `palimpsest/log_level`. Gitignore `clients/godot-observer/.godot/` and web build output. Do not gitignore `project.godot` or `export_presets.cfg`.
  - Logging: `[observer.log] level_set level=%s` at INFO when the logger starts. `[observer.main] client_boot renderer=gl_compatibility` at INFO.
  - Files: `clients/godot-observer/project.godot`, `clients/godot-observer/export_presets.cfg`, `clients/godot-observer/scenes/main.tscn`, `clients/godot-observer/scripts/main.gd`, `clients/godot-observer/scripts/log.gd`, `.gitignore`.

- [x] Task 2: Keep the client out of the Python package.
  - Deliverable: an architecture test fails if `pyproject.toml` package lists include `clients/godot-observer` or a top-level `godot` import root, if any file under `src/` references `clients/godot-observer` or `godot`, or if any `*.gd` under `clients/godot-observer/scripts/` contains `localhost` or `127.0.0.1`. The default unit and V1 regression gates do not launch Godot.
  - Logging: no production logger. The test records the forbidden strings it scanned.
  - Depends on task 1.
  - Files: `tests/architecture/test_godot_client_isolation.py`.

### Phase 2: Protocol Transforms

- [x] Task 3: Parse observer JSON and lock golden payloads.
  - Deliverable: `RefCounted` GDScript models for manifest, frame, world, location, presentation, agent, measures, item, resource, weather, and event. Parsing tolerates an unknown event `type` by returning a structured value with `known=false` instead of raising. A wrong or missing top-level `protocol_version` on manifest, frame, or a known event returns a failure code `unsupported_observer_protocol`. Parse the live wire shape from `src/api/observer_service.py`: `connection_anchors` is a list of `[neighbor_id, {x, y}]` pairs, and cursor `sequence`, `after_tick`, and `after_sequence` may be JSON `null`. Do not require the dict shape used inside `src/observer/layouts/reference-v1.json`. Golden JSON files under `clients/godot-observer/fixtures/protocol/` cover one payload per closed semantic type from `SEMANTIC_EVENT_TYPES`, plus one minimal frame that uses `reference-v1` locations `loc-camp`, `loc-spring`, `loc-grove`, and `loc-ridge` with that wire shape and a null resume cursor. `tests/unit/test_godot_observer_fixtures.py` loads those files and constructs the Python `ObserverEvent` and `ObserverFrame` types so the samples cannot drift from `observer-protocol-v1`. The frame fixture’s `events` array, when present, is history already folded into `world` and is not a second animation list.
  - Logging: `[observer.protocol] parsed kind=%s id_count=%s` at DEBUG. `[observer.protocol] parse_failed reason_code=%s` at ERROR. No measure values at INFO.
  - Depends on task 1.
  - Files: `clients/godot-observer/scripts/protocol/models.gd`, `clients/godot-observer/fixtures/protocol/`, `clients/godot-observer/tests/test_models.gd`, `tests/unit/test_godot_observer_fixtures.py`.

- [x] Task 4: Add cursor, URL, playback, and display-slot rules.
  - Deliverable: pure functions, covered by GDScript tests in `clients/godot-observer/tests/` and a headless runner `clients/godot-observer/tests/run_protocol.gd` (`godot --headless --path clients/godot-observer --script res://tests/run_protocol.gd`). Cursor order is `(tick, sequence)` with a strict greater-than check; duplicate and older events are skipped. URL builder joins an origin and a path and is GET-only. It omits `after_tick` and `after_sequence` when either is null or `after_sequence < 0`, and otherwise appends both. It never substitutes `world.tick` for `after_tick`. WebSocket URL uses `ws` or `wss` from the origin scheme. A resume helper pages an events array of `{count, events, limit}` by the last event’s `(tick, sequence)` until `events.size() < limit`. Playback policy returns a duration for speed 1 and a skip flag at speed 8 or when the pending motion count is greater than 3. Slot display uses `local_x` and `local_y` as layout coordinates when both are present, and the golden-angle fallback in that same space when they are absent. It does not add `screen_position` and does not negate Y. Tests assert the fallback result is not inserted into any request dictionary, and that a null cursor and `after_sequence=-1` produce a URL with neither resume parameter.
  - Logging: `[observer.protocol] cursor_applied tick=%s sequence=%s` at DEBUG. `[observer.protocol] event_skipped reason_code=stale_cursor` at DEBUG. `[observer.net] url_built route=%s` at DEBUG with path only, no token and no origin userinfo. `[observer.playback] motion_skipped speed=%s pending=%s` at DEBUG.
  - Depends on task 3.
  - Files: `clients/godot-observer/scripts/protocol/cursor.gd`, `clients/godot-observer/scripts/protocol/urls.gd`, `clients/godot-observer/scripts/protocol/playback.gd`, `clients/godot-observer/scripts/protocol/slots.gd`, `clients/godot-observer/scripts/net/origin.gd`, `clients/godot-observer/tests/run_protocol.gd`, `clients/godot-observer/tests/test_cursor.gd`, `clients/godot-observer/tests/test_urls.gd`, `clients/godot-observer/tests/test_playback.gd`, `clients/godot-observer/tests/test_slots.gd`.
<!-- Commit checkpoint: tasks 1-4 -->

### Phase 3: Live Session

- [x] Task 5: Bootstrap over HTTP and show loading and error states.
  - Deliverable: `Session` loads manifest, then current state, then renders `world` before any tween. Run id comes from the UI or `palimpsest/run_id`. Layout stays the presentation already embedded in the frame (`reference-v1` on the current stream). `frame.events` is folded history: do not tween it and do not copy it into the live event log. Keep `cursor.after_tick` and `cursor.after_sequence` as the resume pair, including JSON null. Auth header is `x-palimpsest-token` from a gitignored local setting. Loading, `observer_origin_missing`, `unsupported_observer_protocol`, unauthorized, and not-found states are visible in the UI and do not throw. Failed bootstrap does not open the socket.
  - Logging: `[observer.session] bootstrap_started run_id=%s` at INFO. `[observer.session] bootstrap_ready tick=%s` at INFO. `[observer.session] bootstrap_failed reason_code=%s` at ERROR. `[observer.http] get_finished route=%s status=%s` at DEBUG. No token.
  - Depends on tasks 2 and 4.
  - Files: `clients/godot-observer/scripts/net/http_client.gd`, `clients/godot-observer/scripts/net/session.gd`, `clients/godot-observer/scenes/ui/status_bar.tscn`, `clients/godot-observer/scripts/ui/status_bar.gd`.

- [x] Task 6: Stream live events and reconnect from the cursor.
  - Deliverable: after a successful bootstrap, open `/v1/simulations/{run_id}/observer/stream` using the task 4 resume rules. Set `WebSocketPeer.supported_protocols` to `palimpsest.v1` and `palimpsest.token.<token>`. Do not put the token in `handshake_headers`. Handle `hello`, `event`, `tick`, `heartbeat`, `rejected`, and `completion`. `hello` replaces logical `world` when its cursor is newer and does not enqueue `hello.frame.events`. `event` applies logical changes and queues a visual. `tick` starts a state GET that does not wait for tweens; the refresh replaces agents, items, resources, weather, and measures and does not enqueue that frame’s `events`. `rejected` shows `client_mutation_rejected` and sends nothing further. On socket loss, backoff, GET the event gap page by page until a short page, refresh state, then resume the socket at the last applied event. Omit both resume parameters when the cursor is null or `after_sequence < 0`. Close codes 4400, 4401, 4404, and 4409 map to visible errors. An unknown envelope `kind` is logged and ignored. A test resumes from a null cursor without query parameters, and from `(after_tick, after_sequence) = (world.tick, 0)` is rejected by the client before connect because `after_tick` must stay strictly below `world.tick`.
  - Logging: `[observer.stream] socket_opened run_id=%s after_tick=%s after_sequence=%s` at INFO. `[observer.stream] envelope kind=%s tick=%s sequence=%s` at DEBUG. `[observer.stream] socket_closed reason_code=%s` at WARN. `[observer.stream] gap_filled event_count=%s` at INFO. No token and no raw credential subprotocol.
  - Depends on task 5.
  - Files: `clients/godot-observer/scripts/net/stream_client.gd`, `clients/godot-observer/scripts/net/session.gd`, `clients/godot-observer/tests/test_session_cursor.gd`.

### Phase 4: Location Map

- [x] Task 7: Split the view into scenes.
  - Deliverable: `Main` instances `WorldView` and `UILayer`. `WorldView` contains `LocationLayer`, `ConnectionLayer`, `AgentLayer`, `ObjectLayer`, `EffectsLayer`, and a `Camera2D`. Each layer has its own scene and script. `UILayer` instances the status bar from task 5 rather than a second status view. `main.gd` only wires the session to those layers. No layer script parses HTTP.
  - Logging: `[observer.view] scene_ready layer=%s` at DEBUG for each layer.
  - Depends on tasks 1 and 5.
  - Files: `clients/godot-observer/scenes/main.tscn`, `clients/godot-observer/scenes/world_view.tscn`, `clients/godot-observer/scenes/layers/location_layer.tscn`, `clients/godot-observer/scenes/layers/connection_layer.tscn`, `clients/godot-observer/scenes/layers/agent_layer.tscn`, `clients/godot-observer/scenes/layers/object_layer.tscn`, `clients/godot-observer/scenes/layers/effects_layer.tscn`, `clients/godot-observer/scenes/ui/ui_layer.tscn`, and the matching scripts under `clients/godot-observer/scripts/view/` and `clients/godot-observer/scripts/ui/ui_layer.gd`.

- [x] Task 8: Draw zones, names, connections, themes, and resources.
  - Deliverable: each location is a zone from `visual_bounds` scaled by `pixels_per_unit`, drawn at that rectangle in layout space, with `display_name` (fallback `name`). Do not offset the rectangle by `screen_position` and do not negate Y. Theme colors come from a small GDScript catalog keyed by the presentation `theme` string (`camp`, `spring`, `grove`, `ridge`, and a default). Unknown themes use the default and log `theme_unknown`. Connection lines follow `neighbor_ids` only, using each `[neighbor_id, {x, y}]` anchor in layout space when present. Ground items and resources appear in `ObjectLayer`. Resource labels show name, quantity, and unit from the frame. Weather condition tints the matching zone from the frame. Rebuilding the map does not allocate simulation state.
  - Logging: `[observer.locations] map_built location_count=%s connection_count=%s` at DEBUG. `[observer.locations] layout_position_missing location_id=%s` at WARN. `[observer.locations] theme_unknown theme=%s` at DEBUG. Do not log coordinates at INFO.
  - Depends on tasks 4 and 7.
  - Files: `clients/godot-observer/scripts/view/location_layer.gd`, `clients/godot-observer/scripts/view/connection_layer.gd`, `clients/godot-observer/scripts/view/object_layer.gd`, `clients/godot-observer/scripts/presentation/theme_catalog.gd`, `clients/godot-observer/scripts/presentation/scale.gd`.
<!-- Commit checkpoint: tasks 5-8 -->

### Phase 5: Agents, Motion, and Effects

- [ ] Task 9: Place agent tokens in deterministic slots.
  - Deliverable: one placeholder token per agent, keyed by `entity_id`. Color and shape are stable for `agent_id` when it is present, otherwise `entity_id`. The token shows that label, a dead marker when `life_status` is `dead`, and a short activity label for the latest logical event whose acting or target body is this `entity_id`. Tokens in one location use task 4 slot placement in layout space, without adding `screen_position` and without negating Y. Selecting a token stores the `entity_id` locally. Tokens sharing a location do not overlap when slot coordinates exist.
  - Logging: `[observer.agents] tokens_built agent_count=%s` at DEBUG. `[observer.agents] slot_fallback entity_id=%s slot_index=%s` at DEBUG when coordinates were missing. `[observer.agents] selected entity_id=%s` at DEBUG.
  - Depends on tasks 4 and 8.
  - Files: `clients/godot-observer/scripts/view/agent_layer.gd`, `clients/godot-observer/scripts/view/agent_token.gd`, `clients/godot-observer/scripts/presentation/identity.gd`, `clients/godot-observer/scenes/layers/agent_token.tscn`.

- [ ] Task 10: Pan, zoom, and reset the camera.
  - Deliverable: drag on empty map space pans. Mouse wheel and on-screen buttons zoom within a fixed min and max. Reset returns to zoom 1 centered on the selected token, or on the map centroid when nothing is selected. A focus action recenters on the selected token without changing the simulation. `UILayer` also has a client-only playback-speed control that sets the multiplier consumed by the task 4 policy. Changing it does not call the simulation. Input stays in the UI and camera scripts.
  - Logging: `[observer.camera] view_changed zoom=%s reason=%s` at DEBUG for `pan`, `zoom`, `reset`, and `focus`.
  - Depends on task 7.
  - Files: `clients/godot-observer/scripts/view/camera_rig.gd`, `clients/godot-observer/scenes/world_view.tscn`, `clients/godot-observer/scripts/ui/ui_layer.gd`.

- [ ] Task 11: Animate movement without delaying ticks.
  - Deliverable: `AGENT_MOVED` and `AGENT_FLED` (when a destination exists) select the token whose `entity_id` equals `actor_id`, set that agent's logical `location_id` immediately, recompute the destination slot in layout space, and tween the token along the already drawn connection. The tween uses task 4 playback policy, including the speed control from task 10 when that control already exists. A newer logical location replaces the tween target. The WebSocket and the tick-driven state refresh keep running during the tween. Tests on the playback and logical reducer show that applying two moves at high speed ends at the second location without a wait, and that a move does not also replay events embedded in a frame.
  - Logging: `[observer.motion] move_started entity_id=%s origin=%s destination=%s speed=%s` at DEBUG. `[observer.motion] move_snapped entity_id=%s reason_code=%s` at DEBUG. No coordinates at INFO.
  - Depends on tasks 6 and 9.
  - Files: `clients/godot-observer/scripts/protocol/reducer.gd`, `clients/godot-observer/scripts/view/effects_layer.gd`, `clients/godot-observer/tests/test_reducer.gd`.

- [ ] Task 12: Play the remaining event visuals, including weather.
  - Deliverable: effects for every row in Semantic visuals. Select the token by `entity_id`. For `AGENT_DIED`, `NEEDS_APPLIED`, and `EXPOSURE_APPLIED`, that id is `target_id`. For the other types it is `actor_id`. `AGENT_DIED` switches that token to the dead marker even when `actor_id` is null. `WEATHER_CHANGED` pulses the origin zone; the condition tint updates only when the frame refresh arrives. Closed types that are activity-only still set that token's activity label. An unknown `type` does not change positions and does not raise. Applying the golden fixture set plus one extra unknown event leaves the last known logical location intact. Applying a frame that already contains those events in `events` does not move tokens a second time.
  - Logging: `[observer.effects] played type=%s event_id=%s` at DEBUG. `[observer.effects] unknown_event type=%s event_id=%s` at WARN. `[observer.effects] effect_skipped type=%s reason_code=playback_speed` at DEBUG.
  - Depends on task 11.
  - Files: `clients/godot-observer/scripts/protocol/event_router.gd`, `clients/godot-observer/scripts/view/effects_layer.gd`, `clients/godot-observer/tests/test_event_router.gd`.
<!-- Commit checkpoint: tasks 9-12 -->

### Phase 6: Speech, Inspector, Smoke, and Docs

- [ ] Task 13: Show speech bubbles and a durable event log.
  - Deliverable: talk, ask, and tell open a short bubble on the actor. The bubble text is the semantic label plus the other id, never invented speech. The UI event log appends every applied event, including unknown types, in `(tick, sequence)` order, and keeps them after the bubble hides. High playback speed may skip the bubble and must still append the log line.
  - Logging: `[observer.speech] bubble_shown type=%s actor_id=%s` at DEBUG. `[observer.log_view] line_appended tick=%s sequence=%s type=%s` at DEBUG. No message body.
  - Depends on task 12.
  - Files: `clients/godot-observer/scripts/view/effects_layer.gd`, `clients/godot-observer/scenes/ui/event_log.tscn`, `clients/godot-observer/scripts/ui/event_log.gd`.

- [ ] Task 14: Open an inspector when an agent is clicked.
  - Deliverable: the inspector shows identity (`agent_id` and `entity_id`), location display name, `life_status`, inventory summary resolved from frame items (name and kind, or the id when the item is absent), and the latest logical event type for that agent. Health, hunger, thirst, fatigue, and temperature render only when `measures` is present. Clicking empty map space clears the inspector. No memory, emotion, goal, or relationship section, and no call to the relationship route.
  - Logging: `[observer.inspector] opened entity_id=%s` at DEBUG. `[observer.inspector] measures_hidden entity_id=%s reason_code=measures_absent` at DEBUG. No measure values and no token.
  - Depends on tasks 9 and 12.
  - Files: `clients/godot-observer/scenes/ui/inspector.tscn`, `clients/godot-observer/scripts/ui/inspector.gd`.

- [ ] Task 15: Add deterministic fixture playback for visual smoke.
  - Deliverable: `clients/godot-observer/fixtures/smoke/reference_session.json` contains a frame on the reference locations and an ordered event list: an `AGENT_MOVED` from `loc-camp` to `loc-grove`, one sample of each other visual type that the protocol can express, and a final unknown type. A UI action `Play fixture` applies that file with the same reducer and views as the live session and does not open a socket. A GDScript test applies the file at high speed and asserts the moved agent's logical location is the destination and the unknown type is in the log model. Document the headless command. Default pytest does not require the Godot binary; the Python fixture test only checks that the known events in the smoke file still construct `ObserverEvent` and that the unknown type is outside `SEMANTIC_EVENT_TYPES`.
  - Logging: `[observer.fixture] playback_started event_count=%s` at INFO. `[observer.fixture] playback_finished last_tick=%s last_sequence=%s` at INFO.
  - Depends on tasks 12, 13, and 14.
  - Files: `clients/godot-observer/fixtures/smoke/reference_session.json`, `clients/godot-observer/scripts/net/fixture_player.gd`, `clients/godot-observer/tests/test_fixture_playback.gd`, `tests/unit/test_godot_observer_fixtures.py`.

- [ ] Task 16: Document the client for researchers.
  - Deliverable: add `docs/godot-observer.md` and link it from `README.md` and `docs/observer.md`. State the Godot 4.7.2 Compatibility Web target, the `clients/godot-observer/` path, read-only routes, same-origin setup, where to put a local token without committing it, fixture playback, and the headless GDScript command. Replace the sentence that says Godot is not in this repository. Note that animation and camera motion do not change the run. Route this page through the docs checkpoint (`/aif-docs`).
  - Logging: no runtime logger. The page lists the log setting `palimpsest/log_level` and the fields that must stay out of logs (token, seed, utterance text).
  - Depends on tasks 6 and 15.
  - Files: `docs/godot-observer.md`, `docs/observer.md`, `README.md`.
<!-- Commit checkpoint: tasks 13-16 -->
