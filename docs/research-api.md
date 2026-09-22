# Research API

[← Architecture](architecture.md) · [Simulation runner](simulation-runner.md) · [Persistence](persistence.md) · [Back to README](../README.md)

Palimpsest V1 exposes a FastAPI **research and inspection** surface — not a production public service. There is no production frontend.

## Capabilities

Separate credentials gate four capability classes (`PALIMPSEST_API_*`):

| Capability | Purpose |
| --- | --- |
| Simulation control | create / configure / start / tick / run / stop / list / status |
| Objective inspection | world projection, commits/events, agent-visible observations, metrics catalog/documents, replay |
| Streaming | resumable WebSocket progress/events from the durable outbox |
| Subjective debug | owner-scoped memories / beliefs / relationships (disabled by default) |

Secrets use strong `SecretStr` values. Query-string secrets are rejected. Prefer header or WebSocket subprotocol transport.

## REST (`/v1`)

- `POST /v1/simulations` — create/configure with canonical runner-config payload
- `POST /v1/simulations/{run_id}/start|tick|run|stop`
- `GET /v1/simulations` / `GET /v1/simulations/{run_id}` — list/status
- Objective world, commits/events (keyset pagination), agent-visible observation
- Metric catalog and immutable metric documents
- Replay-to-tick endpoints (detached projection; never live `WorldEngine`)

Stable problem-detail errors carry closed reason codes. Lifecycle conflicts return conflict responses without leaking configuration or evidence payloads.

### API versioning (V2 scaffolding)

- Keep **`/v1`** stable. Do **not** introduce `/v2` HTTP routes in this scaffolding plan.
- Introduce `/v2` only when a request/response shape cannot be expressed as optional additive fields on `/v1`.
- WebSocket subprotocol remains `palimpsest.v1` (credentials via header / subprotocol only — never query strings).
- `SimulationManager` stores opaque `config_payload` + fingerprint; decode happens at runner construction.
- Accepted runner config wire versions: `runner-config-v1`, `runner-config-v2` (legacy), and `runner-config-v3` (current write with default-off `V2CapabilityFlags`). Legacy v2 payloads must remain creatable/configurable and constructible.

## Debug security

Subjective debug routes are **disabled by default**. Enabling requires:

- `PALIMPSEST_API_DEBUG_ENABLED=true`
- `PALIMPSEST_API_DEBUG_CREDENTIAL` (required when enabled)

Owner/run scoped, paginated, and absent from logs (no memories, beliefs, relationships, or credentials).

## WebSocket stream

`/v1/simulations/{run_id}/stream`

- Authenticated pre-accept
- Versioned envelopes, one durable monotonic cursor
- Catch-up then live handoff from the PostgreSQL outbox
- Eventless ticks, status/metric/result/error/completion frames
- Bounded per-subscriber queues; slow consumers disconnect without blocking simulation
- Heartbeats and graceful shutdown

`LISTEN/NOTIFY` may wake pollers but is never authoritative.

## Logging

INFO records route template / method / status / request/run IDs and bounded counts. Never log raw paths, query strings, bodies, tokens, seeds, evidence, metrics, prompts, or exception text.

## Verification

```bash
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_api_simulation_manager.py \
  tests/unit/test_api_simulation_routes.py \
  tests/unit/test_api_inspection_routes.py \
  tests/unit/test_api_replay_routes.py \
  tests/unit/test_api_streaming.py -q

# Opt-in PostgreSQL
PALIMPSEST_TEST_DATABASE_URL=<disposable-palimpsest_test-dsn> \
uv run --frozen --python 3.12.14 pytest -m integration \
  tests/integration/test_api_simulation_lifecycle.py \
  tests/integration/test_api_event_pagination.py \
  tests/integration/test_api_debug_scope.py \
  tests/integration/test_api_stream_resume.py \
  tests/integration/test_api_stream_backpressure.py \
  tests/integration/test_v1_api_e2e.py -q
```
