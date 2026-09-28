# Godot observer

[← Read-only observer](observer.md) · [Research API](research-api.md) · [Back to README](../README.md)

The Godot observer is a read-only 2D presentation of a running world. It lives in `clients/godot-observer/` and is not a Python package. Simulation code does not import it. The published API serves the already-exported files at `/` and does not import the client.

Opening the client, moving the camera, or changing playback speed does not change seeds, event ids, or `exact_trajectory_hash`.

## Target

Reference editor and export binary: Godot 4.7.2 stable. The project is 2D, GL Compatibility (`gl_compatibility` on desktop and mobile). The committed export preset is Web, with thread support off. The client uses `HTTPRequest` and `WebSocketPeer` only.

## What it reads

HTTP GET only:

- `/v1/simulations/{run_id}/observer/manifest`
- `/v1/simulations/{run_id}/observer/state`
- `/v1/simulations/{run_id}/observer/events`
- `/v1/simulations/{run_id}/observer/run`
- `/v1/simulations/{run_id}/observer/ticks`

It also opens `/v1/simulations/{run_id}/observer/stream` and never sends a text or binary WebSocket payload. Protocol `observer-protocol-v1` is required. A different `protocol_version` is shown as `unsupported_observer_protocol` and is not applied.

The relationship route is out of scope. The client does not request cognition traces, memories, beliefs, goals, emotions, or utterance text. Speech bubbles show the semantic type and the other agent id, not invented dialogue.

## Same-origin setup

URL code joins an origin string and a path. On a Web export the origin is `window.location.origin`, and `GET /version` fills the status strip. Off Web, a configured `palimpsest/observer_origin` loads that origin's `/version`. With no origin the strip uses the protocol constant `observer-protocol-v1`, the export engine `4.7.2-stable`, the application version from `build-info.json` when the export wrote it, and revision `unknown`.

The four status lines are application version, protocol, export engine, and backend revision. A bad manifest, frame, or known event shows `unsupported_observer_protocol` and is not applied. The log line is `[observer.protocol] parse_failed reason_code=unsupported_observer_protocol`.

`./run.sh` prints `INFO startup_ready url=http://127.0.0.1:8080/`. On a Web export, `/?run_id=<id>` fills the run field and starts the session. The log is `[observer.session] web_run_id_applied run_id=<id>`. The query never carries a token. A URL with no query, or an empty `run_id`, waits for Connect.

Scripts under `clients/godot-observer/scripts/` do not contain a loopback host. There is no second reverse proxy: `/health`, `/version`, `/v1`, and the observer WebSocket stay on the same origin as `index.html`.

## Local token

The HTTP header is `x-palimpsest-token`. The WebSocket subprotocols are `palimpsest.v1` and `palimpsest.token.<token>`. The token is never placed in the query string.

Put a local token in gitignored `clients/godot-observer/override.cfg`:

```ini
[palimpsest]

api_token="replace-me"
observer_origin="https://observer.example"
run_id="run-1"
```

Do not commit that file. `project.godot` leaves `api_token` empty.

## Run id and fixture playback

The run id comes from the field at the top of the window or from `palimpsest/run_id`. Connect loads the manifest, then the current state, then the stream. Folded `frame.events` are history already in `world`. They are not tweened and they are not copied into the live event log.

**Play fixture** applies `clients/godot-observer/fixtures/smoke/reference_session.json` through the same reducer and views. It does not open a socket.

## Timeline controls

The playback row is read-only. None of these controls pause, step, or reseed the simulation, and none of them change the run.

| Control | Effect |
| --- | --- |
| Play | While replaying, step forward through committed events. While live, resume applying events that were held during pause. |
| Pause | Stop playback locally. A live run keeps committing. The socket stays open. |
| Previous Event / Next Event | Move one committed `(tick, sequence)`. They do not wrap at the first or latest event. |
| Previous Tick / Next Tick | Land on the last event of the neighboring tick that has events. |
| Jump to Tick | `GET .../state?tick=` for the start of that tick, and focus the first event of that tick when the log page contains it. |
| Jump to Event | `GET .../state?tick=&through_sequence=` for that committed event. |
| Return to Live | Drop the replay buffer, load the unscoped state, and open the socket at the head cursor. |
| `0.25x` `0.5x` `1x` `2x` `4x` `8x` `16x` | Local tween speed only. Slower than `1x` lengthens motion and speech. `8x` and `16x` step a whole tick and skip tweens. Changing speed does not seek and is not sent to the server. |

Going backward requests a reconstructed frame. It does not play a reverse tween.

## Event log

The log is one bounded page, near 200 lines, replaced on each seek. A line is `tick:sequence type actor target description`. The subject is `target_id` for `AGENT_DIED`, `NEEDS_APPLIED`, and `EXPOSURE_APPLIED`, and `actor_id` otherwise. Labels prefer `agent_id`, then the raw id. Location names prefer `display_name`, then `name`. Clicking a line seeks that event. Utterance text is not printed.

Three filters hide loaded lines and do not request another route:

- agent: actor, target, or label
- event type: exact semantic type
- location: origin, destination, or location name

Empty filters show every loaded line.

## Timeline

The bar shows the viewed event tick and the live tick from `GET .../observer/run`. `AGENT_DIED` marks come from the loaded log window. Selected-agent marks use that same window and stay off until the Selected agent toggle is on. Clicking a mark seeks that event. The client does not page the whole run to paint marks.

## Pause and behind live

Pause does not pause the run. New live events sit in a buffer of at most 256 and are not applied until Play. Event 257 discards that buffer. The status bar shows `behind live` until Return to Live or a successful catch-up. The same status is shown when the viewed event is behind the run head. Return to Live ignores the buffer, reloads the head, and resumes the socket.

A completed seek logs in this shape, with no token:

```text
[observer.session] seek_applied mode=REPLAY tick=4 sequence=1
```

## Headless checks

Godot protocol tests are outside default pytest. Pytest only checks that the golden JSON still constructs `observer-protocol-v1` values and that the smoke file's unknown type is outside the closed semantic list.

```bash
godot --headless --path clients/godot-observer --script res://tests/run_protocol.gd
```

## Logging

`palimpsest/log_level` defaults to `DEBUG` and can be set to `WARN` for a web export without a code edit. Lines look like `[observer.session] bootstrap_ready tick=2`.

These fields stay out of logs:

- token
- seed
- utterance text

Coordinates are not logged at INFO. Relationship scores are not shown or logged.
