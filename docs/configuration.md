# Configuration

[← Previous Page](architecture.md) · [Back to README](../README.md) · [Next Page →](development.md)

All application settings use the **`PALIMPSEST_`** prefix only. Environment variables override a project-root `.env` file (the directory that contains `pyproject.toml`). Missing `.env` is allowed. Importing packages does not read required secrets or connect to PostgreSQL.

## Settings

| Variable | Purpose |
| --- | --- |
| `PALIMPSEST_ENVIRONMENT` | `local` (console logs), `test`, or `production` (JSON logs) |
| `PALIMPSEST_LOG_LEVEL` | Only application log-level setting: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `PALIMPSEST_API_HOST` / `PALIMPSEST_API_PORT` | Bind metadata for operators; Uvicorn in Docker listens on `0.0.0.0:8080` |
| `PALIMPSEST_DATABASE_URL` | Async SQLAlchemy URL, **`postgresql+asyncpg://` only**. Required at runtime startup, not at import |
| `PALIMPSEST_TEST_DATABASE_URL` | Disposable integration-test URL; database **name** must contain `palimpsest_test` and must not be `postgres` / `template0` / `template1` |
| `PALIMPSEST_POOL_SIZE` / `PALIMPSEST_MAX_OVERFLOW` / `PALIMPSEST_POOL_TIMEOUT_SECONDS` | Async pool bounds (`pool_pre_ping` is always on) |
| `PALIMPSEST_DEFAULT_RUN_SEED` | Optional composition default. Always copied into `SimulationRunConfig`; never an implicit global RNG |

Booleans are rejected as integer settings. Invalid environments, pool bounds, seeds, and non-asyncpg URLs fail validation. Credentials are `SecretStr` and are stripped from `repr`, validation errors, and logs.

Alembic loads its URL from validated settings (never from `alembic.ini`). If both `PALIMPSEST_DATABASE_URL` and `PALIMPSEST_TEST_DATABASE_URL` are set and disagree, migration settings fail closed. Integration fixtures bind Alembic to the validated disposable test DSN so a conflicting runtime URL cannot divert the upgrade.

Copy `.env.example` to `.env` for local overrides. Do not commit `.env`.

## Logging

`configure_logging` is idempotent: one owned handler named `palimpsest`, UTC timestamps, exception rendering, isolated context variables. Unrelated handlers are preserved. `uvicorn.access` is set to WARNING so access lines do not duplicate application request records.

| Event | Level | Logger |
| --- | --- | --- |
| `logging_configured` | DEBUG | `infrastructure.logging` |
| `settings_loaded` | DEBUG | `infrastructure.settings` |
| `engine_created`, `session_opened`, `session_closed`, `readiness_check_started`, `engine_disposing`, `engine_disposed` | DEBUG | `infrastructure.database` |
| `request_started`, `request_completed` | DEBUG | `api.request` — `method`, `path`, `status`, `duration_ms`, `request_id` only |
| `run_configured` | DEBUG | `simulation.run` — `run_id`, `seed`, `derivation_version`, `scope` |
| `logging_ready` | INFO | `infrastructure.logging` |
| `app_started`, `app_stopping`, `app_stopped` | INFO | `infrastructure.lifecycle` |
| `database_ready` | INFO | `infrastructure.database` |
| `migration_started`, `migration_completed` | INFO | `infrastructure.migrations` — `revision`, `mode` |
| `malformed_request_id` | WARNING | `api.request` — reason only, never the raw inbound value |
| `readiness_check_failed` | WARNING | `infrastructure.database` |
| `replay_mismatch` | WARNING | `simulation.run` |
| `setup_failed` | ERROR | `infrastructure` |
| `transaction_failed` | ERROR | `infrastructure.database` |
| `unhandled_failure` | ERROR | `api.request` |
| `invalid_setup` | ERROR | `simulation.run` |

### Correlation and provenance

- `X-Request-ID`: inbound value must match `[A-Za-z0-9._-]{1,128}`; otherwise an operational hex id is generated. Echoed on success and error. Cleared after every request. **Not** a simulation id.
- Run logs may include `run_id`, `seed`, `derivation_version`, `stream_scope`.
- Never log: bodies, `Authorization`, arbitrary query strings, wholesale settings, DSNs, credentials, prompts, raw LLM responses, memories, beliefs, communication content, embeddings, SQL parameters, vector values, or random draws.

`PALIMPSEST_TEST_DEBUG` may print concise test-harness DEBUG lines. Tests must not configure application logging during collection.

## Seeds, IDs, and clocks

- `SimulationRunConfig.seed` is required and non-negative (not a bool).
- Named streams: `create_named_stream(config, StreamScope(namespace, names))` via SHA-256 (`v1`). Distinct name tuples do not alias. Process-global `random` is untouched.
- `derive_run_id` / `derive_scoped_id` use the same digest scheme.
- `LogicalClock` uses explicit `Tick` values. Domain contracts do not default to wall-clock or UUID factories.
- Exact LLM replay needs recorded responses or stubs (`LLM_REPLAY_REQUIREMENT = recorded_or_stub`).

## See also

- [Architecture](architecture.md)
- [Development](development.md)
