# Research API

[← Architecture](architecture.md) · [Simulation runner](simulation-runner.md) · [Persistence](persistence.md) · [Back to README](../README.md)

Palimpsest V1 exposes a FastAPI **research and inspection** surface — not a production public service. A researcher SPA is served at **`/research/`** when `PALIMPSEST_RESEARCH_WEB_ROOT` is configured (see [Research UI](research-ui.md)). Godot remains at `/`. Mount `/research/` before the presentation catch-all.

## Capabilities

Separate credentials gate four capability classes (`PALIMPSEST_API_*`):

| Capability | Purpose |
| --- | --- |
| Simulation control | create / configure / start / tick / run / stop / list / status |
| Objective inspection | world projection, commits/events, agent-visible observations, metrics catalog/documents, replay, inspect run index, matrix FS |
| Streaming | resumable WebSocket progress/events from the durable outbox |
| Subjective debug | owner-scoped memories / beliefs / relationships, projections, graph summaries, debugger (disabled by default) |

Secrets use strong `SecretStr` values. Query-string secrets are rejected. Prefer header or WebSocket subprotocol transport.

## REST (`/v1`)

- `POST /v1/simulations` — create/configure with canonical runner-config payload
- `POST /v1/simulations/{run_id}/start|tick|run|stop`
- `GET /v1/simulations` / `GET /v1/simulations/{run_id}` — list/status (`simulation_control`)
- `GET /v1/research/runs` — inspect-scoped read-only run index (`objective_inspection`; Research UI default discovery)
- Objective world, commits/events (keyset pagination), agent-visible observation
- Metric catalog and immutable metric documents
- Subjective **projections** under `subjective_debug`: goals, emotional-state, self-model (identity/goals projection — not a second belief store), theory-of-mind, group-formation, social-norms, social-conventions, cultural-narratives; plus metadata-safe `memories/summary` and `beliefs/summary` for graphs (count-only `SubjectivePageOut` pages stay for existing clients)
- Read-only matrix filesystem under `PALIMPSEST_RESEARCH_MATRIX_ROOT`: `GET /v1/research/matrices` and allowlisted `manifest.json` / `cells/*` / `aggregate.json` / `metric-summary.json` (path traversal fail-closed; no `analysis` import; no batch starts)
- Replay-to-tick endpoints (detached projection; never live `WorldEngine`)
- Read-only observer manifest, state, events, ticks, run metadata, and live stream. See [Read-only observer](observer.md). Presentation coordinates are not simulation coordinates. Researcher relationship summaries stay on the debug capability.
- Observer event pages accept additive optional filters (`agent_id`, `event_type`, `location_id`) and `catch_up=true` for multi-page reconnect fill within `PALIMPSEST_API_MAX_PAGE_SIZE`. Filter `agent_id` matches events where that id equals **`actor_id` or `target_id`** after adapt (presentation filter; includes target-only rows such as `AGENT_DIED`). Protocol remains `observer-protocol-v1` — no layout/protocol rename for scale.
- Godot observer branch navigation uses the existing lineage GETs (`/branches`, `/branch`, `/branch/fork-point`) under `objective_inspection` and replaces one `ObserverSource` at a time. Local researcher bookmarks stay in the client (`user://`); they are not authoritative history and have no server API.
- Research causal debugger GET routes under `/v1/simulations/{run_id}/debugger/…` require `subjective_debug` (observational; tracing-off → `200` + `unavailable`). See [Research causal debugger](research-causal-debugger.md).
- Research **simulation branches** (deterministic forks):
  - `POST /v1/simulations/{parent_run_id}/branches` — create one child from `fork_tick` + exactly one closed `ResearchIntervention` (`simulation_control`; idempotent on identical fingerprint)
  - `GET /v1/simulations/{run_id}/branches` — list children (keyset)
  - `GET /v1/simulations/{run_id}/branch` — parent lineage or `404`/`branch_root`
  - `GET /v1/simulations/{run_id}/branch/fork-point` / `…/branch/state` — fork cursor + thin run envelope
  - `POST /v1/simulations/branches/compare` — detached journal timeline compare (`objective_inspection`)
  - Research forks are **not** agent `CounterfactualScenario` / prospective rollouts; parent history is never rewritten.

Stable problem-detail errors carry closed reason codes. Lifecycle conflicts return conflict responses without leaking configuration or evidence payloads.

### API versioning (V2 scaffolding)

- Keep **`/v1`** stable. Do **not** introduce `/v2` HTTP routes in this scaffolding plan.
- Introduce `/v2` only when a request/response shape cannot be expressed as optional additive fields on `/v1`.
- WebSocket subprotocol remains `palimpsest.v1` (credentials via header / subprotocol only — never query strings).
- `SimulationManager` stores opaque `config_payload` + fingerprint; decode happens at runner construction.
- Accepted runner config wire versions: `runner-config-v1`…`runner-config-v22` (mode-driven), with default write **`runner-config-v4`** (default-off `V2CapabilityFlags` + disabled tracing). Planned `runner-config-v23` carries sibling root `v3_capability_flags` (V3 scaffolding; writers emit v23 only when some V3 flag is true). Legacy v1/v2 payloads must remain creatable/configurable and constructible.

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

Observer live WebSocket (`/v1/simulations/{run_id}/observer/stream`) uses the same backpressure pattern: per-subscriber bounded queues (`PALIMPSEST_OBSERVER_STREAM_QUEUE_SIZE`), catch-up batch size (`PALIMPSEST_OBSERVER_CATCHUP_PAGE_SIZE`, capped by `api_max_page_size`), and `slow_consumer` disconnect of that subscriber only. Simulation ticks must not await observer drains. After a client discard-behind-live, reconnect via `GET .../observer/events` (optionally `catch_up=true`) then resume the socket — scientific history stays complete; presentation coalescing lives only in Godot / observer projection helpers.

## Long-run research settings (opt-in)

Defaults preserve short V1 runs. Scale knobs are settings / helpers, not capability flags:

| Knob | Role |
| --- | --- |
| `long_run_checkpoint_policy` / `long_run_persistence_spec` | Enable write-time snapshot cadence (e.g. every 100/500/1000 ticks); no in-DB snapshot DELETE |
| `PALIMPSEST_OBSERVER_STREAM_QUEUE_SIZE` / `PALIMPSEST_OBSERVER_CATCHUP_PAGE_SIZE` | Observer WS backpressure and reconnect batching |
| `PALIMPSEST_MEMORY_RETRIEVE_MAX_CANDIDATES` | SQL candidate cap before `rank_traces` (default 4096) |
| `PALIMPSEST_LLM_MAX_CONCURRENCY` | Process-wide `generate` semaphore (default 1); parallel agent prepare stays off |
| `PALIMPSEST_COGNITION_TRACE_SOFT_CAP_*` | Optional soft stop-append for traces (fail-soft; never DELETE rows) |

See [Persistence](persistence.md), [Observer](observer.md), [Memory reconstruction](memory-reconstruction.md), and [Development](development.md) (`pytest -m scale`) for details. Do not prune append-only tables in place; do not introduce Kafka/K8s for this surface.

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
