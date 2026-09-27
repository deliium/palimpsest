# Read-only observer

[← Architecture](architecture.md) · [Research API](research-api.md) · [Back to README](../README.md)

The observer shows a run to a human or a future Godot client. It does not decide what the run does. Godot is not in this repository. `simulation.WorldEngine` remains the only authority that commits a tick. Presentation coordinates come from a layout catalog and are not simulation coordinates.

Protocol version: `observer-protocol-v1`. Layout documents use `observer-layout-v1`. The default catalog id is `reference-v1`.

## Authority split

| Piece | Role |
| --- | --- |
| `WorldEngine` | Commits objective events and the world. |
| `simulation.observer_facts` | Copies locations, bodies, items, resources, weather, and registrations after a fold. No seed field. |
| `observer` | Adapts events and projects frames. It does not call engine methods that commit ticks. |
| `api` | Serves the frames over HTTP and WebSocket. |

`simulation`, `world`, `agents`, `memory`, `social`, `llm`, `persistence`, and `experiments` do not import `observer`.

## Routes

All HTTP methods are GET. The capability is `objective_inspection` except the relationship route, which requires `subjective_debug`.

| Path | Response |
| --- | --- |
| `GET /v1/simulations/{run_id}/observer/manifest` | Layout and protocol identity |
| `GET /v1/simulations/{run_id}/observer/state` | Current frame |
| `GET /v1/simulations/{run_id}/observer/state?tick=` | Frame at that tick |
| `GET /v1/simulations/{run_id}/observer/events` | Adapted events after an exclusive cursor |
| `GET /v1/simulations/{run_id}/observer/ticks` | Tick summaries |
| `GET /v1/simulations/{run_id}/observer/events/{event_id}` | One adapted event |
| `GET /v1/simulations/{run_id}/observer/run` | Run metadata without seed or credentials |
| `GET /v1/simulations/{run_id}/observer/agents/{agent_id}/relationships` | Researcher summaries when debug is on |
| `WS /v1/simulations/{run_id}/observer/stream` | Live envelopes |

Optional `layout_id` defaults to `reference-v1`. Event cursors are `after_tick` and `after_sequence` together, or neither. An incomplete pair returns `incomplete_event_cursor`. A cursor at or past the high water returns `cursor_ahead_of_high_water`.

## Live and replay

A live frame uses `scene_at_tick` with no target, which is the durable head. A `tick` query builds a new frame from a fresh replay to that tick. Seeking does not append events and does not change the clock. A tick past the high water returns the existing unreachable replay status.

The snapshot `next_tick` is the replay cursor. Events folded for a target have `event.tick` strictly before that cursor.

## Reconnect

The socket authenticates like the inspection stream: capability `objective_inspection`, subprotocol `palimpsest.v1`, no query-string credential. It polls the ordered event journal. It does not subscribe to `StreamFanout`.

The first envelope is `hello` (manifest, current frame, cursor). Later envelopes are `event`, `tick` when the high water moves, `heartbeat`, and `completion`. A client text frame returns `rejected` with `client_mutation_rejected` and does not change the run. A full subscriber queue disconnects that client and does not block tick commit.

A client that missed events loads `GET .../observer/events` for the exclusive gap, then resumes the socket at the last event it applied. The next session does not repeat those events.

## Layout and privacy

Two catalogs can place the same location at different screen positions. Neighbor ids, life status, holders, and action outcomes stay the ones committed by the engine.

Ordinary manifest, state, event, tick, run, and stream payloads have no relationship, memory, belief, goal, emotion, or utterance field. Relationship dimension scores are available only on the researcher route, and only when subjective debug is enabled. That route copies stored dimension values and drops evidence rows. When debug is off the response is `debug_disabled`.
