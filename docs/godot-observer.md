# Godot observer

[← Read-only observer](observer.md) · [Research API](research-api.md) · [Back to README](../README.md)

The Godot observer is a read-only 2D presentation of a running world. It lives in `clients/godot-observer/` and is not a Python package. Simulation code does not import it, and FastAPI does not serve the web export.

Opening the client, moving the camera, or changing playback speed does not change seeds, event ids, or `exact_trajectory_hash`.

## Target

Reference editor and export binary: Godot 4.7.2 stable. The project is 2D, GL Compatibility (`gl_compatibility` on desktop and mobile). The committed export preset is Web, with thread support off. The client uses `HTTPRequest` and `WebSocketPeer` only.

## What it reads

HTTP GET only:

- `/v1/simulations/{run_id}/observer/manifest`
- `/v1/simulations/{run_id}/observer/state`
- `/v1/simulations/{run_id}/observer/events`
- `/v1/simulations/{run_id}/observer/run`

It also opens `/v1/simulations/{run_id}/observer/stream` and never sends a text or binary WebSocket payload. Protocol `observer-protocol-v1` is required. A different `protocol_version` is shown as `unsupported_observer_protocol` and is not applied.

The relationship route is out of scope. The client does not request cognition traces, memories, beliefs, goals, emotions, or utterance text. Speech bubbles show the semantic type and the other agent id, not invented dialogue.

## Same-origin setup

URL code joins an origin string and a path. On a Web export the origin is `window.location.origin`. Off Web it is the project setting `palimpsest/observer_origin`. An empty origin shows `observer_origin_missing`. Scripts under `clients/godot-observer/scripts/` do not contain a loopback host.

Host the Web export on the same origin as the API with a reverse proxy. The API does not mount the client.

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
