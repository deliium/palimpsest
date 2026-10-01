# Read-only observer

[← Architecture](architecture.md) · [Research API](research-api.md) · [Back to README](../README.md)

The observer shows a run to a human or to the read-only [Godot observer](godot-observer.md). It does not decide what the run does. The client lives in `clients/godot-observer/` and is not part of the Python package. `simulation.WorldEngine` remains the only authority that commits a tick. Presentation coordinates come from a layout catalog and are not simulation coordinates. Camera motion and playback speed do not change the run.

Protocol version: `observer-protocol-v1`. Layout documents use `observer-layout-v1`. The default catalog id is `reference-v1`.

## Authority split

| Piece | Role |
| --- | --- |
| `WorldEngine` | Commits objective events and the world. |
| `simulation.observer_facts` | Copies locations, bodies, items, resources, weather, and registrations after a fold. No seed field. |
| `observer` | Adapts events and projects frames. It does not call engine methods that commit ticks. |
| `api` | Serves observer frames over HTTP and WebSocket, and serves the prebuilt presentation tree at `/` when `PALIMPSEST_PRESENTATION_WEB_ROOT` is set. It does not import the client. |

`simulation`, `world`, `agents`, `memory`, `social`, `llm`, `persistence`, and `experiments` do not import `observer`.

## Production facts

A frame may include `structures`. Each record has `structure_id`, `location_id`, `kind`, `integrity`, `stored_quantity`, and an optional presentation (`visual_category`, `icon_key`, `size_category`) from `observer.presentation`. Missing catalog rows leave presentation empty. Presentation is not stored on `Item`, `Resource`, `Structure`, `Location`, or `WorldEvent`.

The six production semantic types are `RESOURCE_HARVESTED`, `CRAFT_STARTED`, `ITEM_CRAFTED`, `STRUCTURE_BUILT`, `STRUCTURE_REPAIRED`, and `ITEM_STORED`. `ObserverEvent` adds `recipe_id` and `structure_id` only when they are set. Protocol version stays `observer-protocol-v1`. Godot is not required to read the projection. The current client ignores unknown event types and unknown world keys, so a frame that adds `structures` still parses as protocol v1.

## Environment tokens

When a run has an environmental dynamics spec, a frame at any tick carries the current season, the temperature band at each location, and the hazards active at each location. A dynamics-off frame omits those keys. Resource `quantity` is the folded quantity. Depleted means `quantity == 0`.

The six environment semantic types are `SEASON_CHANGED`, `TEMPERATURE_BAND_CHANGED`, `RESOURCE_NODE_DEPLETED`, `RESOURCE_NODE_RECOVERED`, `ENVIRONMENTAL_HAZARD_STARTED`, and `ENVIRONMENTAL_HAZARD_ENDED`. `public_mapping` includes `season`, `temperature_band`, and `hazard_kind` only when they are set. Domain events and frames do not carry color, sprite, pixel, or coordinate commands.

The Godot client replaces its world from `state_tick` through `world_replaced`. `theme_catalog.gd` maps the season, weather, band, hazard, and depleted tokens to local colors after that replacement. It does not read a color or a sprite from the server.

`observer.project` and `observer.adapt` log `environment_projected`. An unknown kind logs `unknown_event_kind`. A presentation command logs `presentation_instruction_forbidden`.

Visible structures use the same content visibility threshold as local resources (`0.5`). The actor always sees their own production occurrence. `recipe_id` is a public fact for that actor and for a bystander who passes the visibility check.

## Routes

All HTTP methods are GET. The capability is `objective_inspection` except the relationship route, which requires `subjective_debug`.

| Path | Response |
| --- | --- |
| `GET /v1/simulations/{run_id}/observer/manifest` | Layout and protocol identity |
| `GET /v1/simulations/{run_id}/observer/state` | Current frame |
| `GET /v1/simulations/{run_id}/observer/state?tick=` | Frame at the start of that tick |
| `GET /v1/simulations/{run_id}/observer/state?tick=&through_sequence=` | Frame through one committed event |
| `GET /v1/simulations/{run_id}/observer/events` | Adapted events after an exclusive cursor |
| `GET /v1/simulations/{run_id}/observer/ticks` | Tick summaries |
| `GET /v1/simulations/{run_id}/observer/events/{event_id}` | One adapted event |
| `GET /v1/simulations/{run_id}/observer/run` | Run metadata without seed or credentials |
| `GET /v1/simulations/{run_id}/observer/agents/{agent_id}/relationships` | Researcher summaries when debug is on |
| `WS /v1/simulations/{run_id}/observer/stream` | Live envelopes |

Optional `layout_id` defaults to `reference-v1`. Event cursors are `after_tick` and `after_sequence` together, or neither. An incomplete pair returns `incomplete_event_cursor`. A cursor at or past the high water returns `cursor_ahead_of_high_water`.

## Live and replay

A live frame uses `scene_at_tick` with no target, which is the durable head. A `tick` query builds a new frame from a fresh replay to that tick. Seeking does not append events and does not change the clock. A tick past the high water returns the existing unreachable replay status.

The snapshot `next_tick` is the replay cursor. Events folded for a tick-only target have `event.tick` strictly before that cursor. That tick-only query is unchanged: `world.tick` is the requested tick, and omitting `tick` is still the live head.

`through_sequence` is optional and requires `tick`. The fold includes every committed event with `(event.tick, event.sequence) <= (tick, through_sequence)`. It is a read-only prefix of that tick: the server does not write a snapshot and does not keep the restored engine. A shorter prefix keeps the start-of-tick clock and revision, while still showing the occupancy, items, resources, weather, and life status those events produced. When the prefix is the whole tick, the frame matches `GET .../state?tick={event_tick + 1}`, including `world.tick`.

`through_sequence` without `tick` is `incomplete_event_cursor`. A pair past the durable head is `cursor_ahead_of_high_water`. A pair that is not a committed event is `observer_event_not_found`. There is no inverse event. Playback speed is never a query parameter. These reads do not change the run.

## Reconnect

The socket authenticates like the inspection stream: capability `objective_inspection`, subprotocol `palimpsest.v1`, no query-string credential. It polls the ordered event journal. It does not subscribe to `StreamFanout`.

The first envelope is `hello` (manifest, current frame, cursor). Later envelopes are `event`, `tick` when the high water moves, `heartbeat`, and `completion`. A client text frame returns `rejected` with `client_mutation_rejected` and does not change the run. A full subscriber queue disconnects that client and does not block tick commit.

A client that missed events loads `GET .../observer/events` for the exclusive gap, then resumes the socket at the last event it applied. The next session does not repeat those events.

## Layout and privacy

Two catalogs can place the same location at different screen positions. Neighbor ids, life status, holders, and action outcomes stay the ones committed by the engine.

Ordinary manifest, state, event, tick, run, and stream payloads have no relationship, memory, belief, goal, emotion, or utterance field. Relationship dimension scores are available only on the researcher route, and only when subjective debug is enabled. That route copies stored dimension values and drops evidence rows. When debug is off the response is `debug_disabled`.
