# Implementation Plan: V1 Project Foundation

Branch: feature/v1-project-foundation
Created: 2026-09-13

## Roadmap Linkage

Milestone: **M1 — V1 Project Foundation** (see `.ai-factory/ROADMAP.md`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Goal

Create a Python 3.12+ modular-monolith foundation for reproducible, discrete, text-based multi-agent AI society experiments. Establish package boundaries, typed domain contracts, configuration, persistence, API, observability, containers, and tests without implementing simulation behavior.

## Architectural Invariants

1. World state is authoritative.
2. Agents receive immutable observations, never `WorldState`.
3. Objective world state and subjective agent state remain separate.
4. Every agent action is structured and typed.
5. LLM output is untrusted input and cannot mutate world state directly.
6. Objective `WorldEvent` values are immutable.
7. Agent memories and beliefs are mutable and may be incorrect.
8. Memory is agent-scoped and is never shared automatically.
9. Information crosses agent boundaries only through perception and explicit communication.
10. Randomness is injected and derived from an explicit simulation seed.
11. Cognition is defined behind a strategy protocol so alternative cognitive architectures can use the same world contracts.

## Dependency Rules

- `world` owns opaque entity identity, authoritative `WorldState`, observations, typed action requests, action outcomes, and immutable objective events. It imports no other bounded module.
- Base `agents` modules own agent identity and subjective state and may depend only on agent-facing `world` value types. They must not import `agents.cognition`.
- `memory` and `social` may depend on public `agents` identity types and immutable `world` value types; they remain independent of each other and never expose shared mutable state.
- `llm` is provider-neutral and imports no domain module. It returns validated response data only.
- `agents.cognition` is a separate leaf layer: it may consume public contracts from base `agents`, agent-facing `world`, `memory`, `social`, and `llm`; it returns non-authoritative action proposals and cannot receive mutable world state, world transition capabilities, or persistence adapters.
- `simulation` is the future application orchestrator and may depend on `world`, base `agents`, `agents.cognition`, `memory`, `social`, and `llm` through public contracts. It must not import `api` or `analysis`. This plan adds ports and deterministic primitives only, not a simulation loop.
- `api` may depend on public `simulation` application contracts and technical infrastructure, but it cannot mutate domain state directly.
- `analysis` is read-only and may consume immutable world events and simulation export contracts, never live aggregates or mutable repositories.
- `infrastructure` contains technical adapters for settings, logging, and PostgreSQL and imports no domain policy. Domain modules do not import it; the API composition root wires technical resources to application ports.
- Cross-module imports target documented public facade modules or names listed in package `__all__`; private modules and transitive re-exports are not cross-boundary APIs.
- `world/_state.py` and `world/_transitions.py` are authority-facing and are not re-exported. Only `simulation` may import them; other modules may use only agent-facing world contracts.
- Automated import-linter and AST checks enforce the complete allowlist, the `agents`/`agents.cognition` distinction, private-world authority, type-checking imports, public re-exports, framework leakage, and prohibited nondeterministic calls. These checks prevent accidental dependency violations, not hostile reflective Python code.

## Scope Exclusions

- No tick loop, scheduler, action-resolution algorithm, world geography, perception algorithm, communication behavior, agent policy, prompt, memory retrieval behavior, social dynamics, or analysis metric.
- No production LLM provider integration or domain persistence schema beyond the pgvector extension bootstrap and Alembic version table.
- No Kafka, Kubernetes, Celery, Neo4j, Pinecone, Qdrant, CrewAI, AutoGen, microservices, worker processes, or event broker.
- No implicit global random seed, wall-clock dependency in domain contracts, automatic memory sharing, or direct deserialization of LLM output into world mutations.

## Foundation Decisions

- Use `uv` with a committed `uv.lock` and Hatchling as the PEP 517 build backend. Install with lock enforcement and without re-resolution in development and containers.
- Declare Python `>=3.12`; pin one Python 3.12 patch release as the reference development/container environment. This establishes Python 3.12 as the tested baseline without claiming compatibility with every future Python release.
- Keep the explicitly requested top-level bounded packages under `src/`. Package discovery must include only project-owned packages, and installed-wheel tests must detect missing or colliding packages.
- Use Pydantic v2 at validation/serialization boundaries, frozen dataclasses or frozen Pydantic models with immutable nested fields for immutable domain values, and `Protocol` for ports. Boundary models reject unknown fields.
- Treat operational timestamps and request IDs as infrastructure metadata. They never become simulation IDs, event ordering, domain timestamps, or random seeds.
- Use `PALIMPSEST_` as the only settings prefix. Environment variables override `.env`; imports never read required secrets or connect to external services.
- Integration tests require an explicit `PALIMPSEST_TEST_DATABASE_URL`, validate that it targets a disposable test database, and fail safely rather than migrating an ambiguous database.
- Use a pinned pgvector PostgreSQL 17 image for the reference stack. Development migration credentials may create the extension; production privilege design is deferred and documented.

## Commit Plan

- **Commit 1** (after tasks 1-4): `feat: establish project and domain boundaries`
- **Commit 2** (after tasks 5-8): `feat: add reproducible runtime infrastructure`
- **Commit 3** (after tasks 9-11): `feat: bootstrap api and container stack`

## Tasks

### Phase 1: Project and Architecture Foundation

- [x] Task 1: Bootstrap Python packaging, dependencies, and test tooling
  - Deliverable: Create a Hatchling-based Python `>=3.12` `src`-layout project managed by `uv`. Declare FastAPI, Uvicorn, Pydantic v2, `pydantic-settings`, `SQLAlchemy[asyncio]` 2.x, Alembic, `asyncpg`, pgvector, and structlog as runtime dependencies; place httpx, pytest, pytest-asyncio, Hypothesis, pytest-cov, Ruff, mypy, and import-linter in development/test groups. Commit `uv.lock`; configure locked installs, strict pytest markers, asyncio mode/loop scope, linting, typing, coverage, and package discovery.
  - Files: `pyproject.toml`, `uv.lock`, `.python-version`, `.gitignore`, `tests/conftest.py`.
  - Expected behavior: A pinned Python 3.12 reference environment installs without changing the lock; unit tests cannot invoke Docker or PostgreSQL; a wheel builds, installs in a clean environment, and imports all project packages from outside the repository root.
  - Logging requirements: Establish `PALIMPSEST_LOG_LEVEL` as the only application log-level setting; test bootstrap may emit concise DEBUG diagnostics only when requested and must not configure application logging during collection.
  - Dependencies: None.

- [x] Task 2: Create bounded package skeletons and executable dependency constraints
  - Deliverable: Create side-effect-free packages at `src/world/`, `src/agents/`, `src/agents/cognition/`, `src/memory/`, `src/social/`, `src/llm/`, `src/simulation/`, `src/api/`, `src/analysis/`, and `src/infrastructure/`. Encode the complete Dependency Rules in import-linter configuration and a focused AST checker. Restrict direct `random` use to `simulation/randomness.py` with private `random.Random` instances; prohibit global random functions, wall-clock/UUID defaults in domain code, provider SDK imports, ORM/FastAPI leakage, forbidden `TYPE_CHECKING` references, and private authority re-exports.
  - Files: `src/*/__init__.py`, `src/agents/cognition/__init__.py`, `pyproject.toml`, `tests/architecture/test_import_boundaries.py`, `tests/architecture/test_boundary_checker.py`.
  - Expected behavior: Every package imports without side effects; the real source tree satisfies the allowlist; temporary invalid fixtures prove that the checker catches cycles, base-agents-to-cognition imports, private world-state access, forbidden re-exports, and nondeterministic calls while allowing the reviewed RNG adapter.
  - Logging requirements: Package imports must emit no logs. Architecture test failures must identify the source module, imported target, violated rule, and file location; successful checks remain quiet outside DEBUG test output.
  - Dependencies: Task 1.

- [x] Task 3: Define world authority and agent-facing contracts
  - Deliverable: Separate authority-facing `WorldState`/transition capabilities from agent-facing opaque `EntityId`, `WorldRevision`, deeply immutable `Observation`, non-authoritative `ActionProposal`, trusted `ActionRequest`, `ActionOutcome`, and immutable `WorldEvent` contracts. Keep concrete action kinds and resolution behavior deferred. Define agent identity and subjective `AgentState` without exposing state-owned collections or callbacks; require explicit translation between `AgentId` and world `EntityId` at the orchestration boundary.
  - Files: `src/world/identifiers.py`, `src/world/observations.py`, `src/world/actions.py`, `src/world/events.py`, `src/world/_state.py`, `src/world/_transitions.py`, `src/world/__init__.py`, `src/agents/models.py`, `src/agents/contracts.py`, `src/agents/__init__.py`, `tests/unit/test_world_agent_contracts.py`, `tests/architecture/test_world_authority.py`.
  - Expected behavior: `WorldState` and transition capabilities are absent from public exports and rejected in agents, cognition, memory, social, LLM, API, and analysis imports/annotations; observations and events are deeply immutable and defensively detached from source data; only a trusted world gateway accepts `ActionRequest`, never an `ActionProposal` or matching raw mapping.
  - Logging requirements: Pure values and protocols emit no logs. Callers may log proposal/request IDs, actor IDs, revisions, validation stage, and outcome category at DEBUG, but never full state, observations, action payloads, or private mutation details.
  - Dependencies: Tasks 1-2.

- [x] Task 4: Define subjective-state, communication, LLM, and cognition boundaries
  - Deliverable: Define owner-bound mutable memory/belief aggregates, deeply immutable snapshots, typed owner-validating writes, and opaque immutable communication envelopes that cannot contain memory records, agent state, arbitrary `Any`, or mutable containers. Separate provider-valid but untrusted `LLMResponse` from cognition-produced `ActionProposal`; define an architecture-neutral `CognitionStrategy` that receives immutable observation/perspective context and no LLM, repository, social graph, `WorldState`, or mutation capability in its public signature.
  - Files: `src/memory/models.py`, `src/memory/contracts.py`, `src/social/models.py`, `src/social/contracts.py`, `src/llm/models.py`, `src/llm/contracts.py`, `src/agents/cognition/contracts.py`, affected package `__init__.py` files, `tests/unit/test_subjective_state_contracts.py`, `tests/unit/test_llm_trust_boundary.py`, `tests/typecheck/cognition_strategies.py`.
  - Expected behavior: Ownership IDs cannot be reassigned; mutable defaults and payloads are never shared across agents; reads return defensive immutable snapshots; cross-owner writes fail; transport-valid LLM output cannot be passed to the world gateway; deterministic scripted and stub LLM-backed strategies satisfy the same protocol without changing its signature.
  - Logging requirements: Pure contracts emit no logs. Adapter callers may log owner/correlation IDs, model/provider names, validation stage, and token counts at DEBUG/INFO; never log prompts, raw responses, memories, beliefs, communication content, credentials, or embeddings.
  - Dependencies: Tasks 2-3.

<!-- Commit checkpoint: tasks 1-4 -->

- [x] Task 5: Establish deterministic run primitives and read-only exports
  - Deliverable: Define non-optional `SimulationRunConfig.seed`, run/export metadata, a logical tick clock, deterministic namespaced ID generation, and versioned named random-stream derivation from canonical inputs using a stable digest rather than Python `hash()`. Restrict randomness to independent `random.Random` instances; add read-only analysis event/export source protocols. Record effective seed and derivation version while documenting that exact external LLM replay requires recorded responses or deterministic stubs.
  - Files: `src/simulation/models.py`, `src/simulation/contracts.py`, `src/simulation/randomness.py`, `src/simulation/identifiers.py`, `src/simulation/clock.py`, `src/analysis/contracts.py`, affected package `__init__.py` files, `tests/unit/test_reproducibility_contracts.py`, `tests/unit/test_analysis_contracts.py`.
  - Expected behavior: The same canonical seed/scope inputs produce golden streams and IDs regardless of stream creation or agent scheduling order; distinct scopes do not alias; global RNG state remains unchanged; booleans/invalid seeds and omitted domain IDs/times are rejected; operational HTTP/log metadata cannot populate domain identifiers.
  - Logging requirements: Pure deterministic primitives emit no logs. The composition boundary may log run ID, effective seed, derivation version, and stream scope at DEBUG, never random values or full exported events; replay/provenance mismatches are WARNING and invalid setup is ERROR.
  - Dependencies: Tasks 2-4.

### Phase 2: Runtime Infrastructure

- [x] Task 6: Implement settings, environment handling, and structured logging
  - Deliverable: Define strict Pydantic settings for environment, API, logging, async PostgreSQL URL/pool bounds, test database safety, and an optional composition-layer seed default that is always copied into explicit run configuration. Load `PALIMPSEST_` environment variables with precedence over a documented project-root `.env` lookup without requiring secrets at import time. Configure idempotent stdlib/structlog integration, console output locally, JSON elsewhere, UTC operational timestamps, exception rendering, and isolated context variables.
  - Files: `src/infrastructure/settings.py`, `src/infrastructure/logging.py`, `.env.example`, `tests/unit/test_settings.py`, `tests/unit/test_logging.py`.
  - Expected behavior: App startup clearly rejects missing runtime database configuration; invalid environments, pool bounds, seeds, and non-`postgresql+asyncpg` URLs fail; booleans are rejected as integer settings; environment overrides `.env`; credentials remain absent from model representations, validation errors, normal logs, and exceptions; repeated setup owns one handler without duplicate records.
  - Logging requirements: Emit secret-safe bootstrap details at DEBUG, major lifecycle events at INFO, recoverable inconsistencies at WARNING, and setup failures at ERROR. Preserve unrelated handlers where possible and prevent duplicate Uvicorn/application request records. Never serialize settings wholesale or log DSNs, credentials, bodies, LLM data, memories, or embeddings.
  - Dependencies: Tasks 1, 2, and 5.

- [x] Task 7: Add asynchronous SQLAlchemy database lifecycle infrastructure
  - Deliverable: Add SQLAlchemy 2 async engine/session factories, declarative metadata with deterministic naming conventions, explicit transaction ownership, and a `SELECT 1` readiness probe. Engine construction must not connect; request session helpers close on success, roll back and close on failure, and never auto-commit application work.
  - Files: `src/infrastructure/database.py`, `src/infrastructure/orm.py`, `tests/unit/test_database_configuration.py`, `tests/integration/test_database.py`.
  - Expected behavior: Pool bounds, `pool_pre_ping`, session lifecycle, readiness, and disposal are covered; unit tests use fakes without external I/O; integration tests use only a validated disposable `PALIMPSEST_TEST_DATABASE_URL` and isolate their schema/session state.
  - Logging requirements: Log engine/session lifecycle and readiness boundaries at DEBUG, successful connectivity at INFO, transient readiness failures at WARNING, and connection/transaction failures at ERROR. Redact DSNs, credentials, SQL parameters, and vector values.
  - Dependencies: Tasks 1, 2, and 6.

- [x] Task 8: Bootstrap Alembic and the pgvector integration-test lifecycle
  - Deliverable: Configure async Alembic with model metadata imports, type comparison, and a URL supplied programmatically from validated settings rather than stored in `alembic.ini`. Add an initial migration containing `CREATE EXTENSION IF NOT EXISTS vector`, a documented no-op downgrade, and no application tables. Build a guarded integration fixture that verifies a test-database naming marker before destructive setup, handles session isolation, and requires extension-creation privilege.
  - Files: `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/0001_enable_pgvector.py`, `tests/integration/conftest.py`, `tests/integration/test_migrations.py`.
  - Expected behavior: An empty PostgreSQL 17/pgvector database upgrades to exactly one head; a repeated `upgrade head` succeeds; `vector` exists; no simulation tables exist; `metadata.create_all()` is never used; unsafe or ambiguous database targets fail before migration; local prerequisite skipping is explicit and CI integration runs require the database.
  - Logging requirements: Log revision/start/completion metadata at INFO, guarded local skips and privilege limitations at WARNING, and migration failures at ERROR with redacted exception context. Never persist or print the expanded database URL.
  - Dependencies: Tasks 6-7.

<!-- Commit checkpoint: tasks 5-8 -->

### Phase 3: API and Containers

- [x] Task 9: Bootstrap FastAPI application lifecycle and health endpoint
  - Deliverable: Implement an injectable `create_app(settings=None, database_factory=None)` composition root, configure logging before application events, create/store database resources during lifespan, dispose them on shutdown and partial-startup failure, and expose `GET /health` with exact payload `{"status": "ok"}` as database-independent liveness. Add `X-Request-ID` middleware that accepts only bounded safe inbound values, otherwise generates an operational ID, returns it on success/error responses, and clears context after every request.
  - Files: `src/api/app.py`, `src/api/routes/__init__.py`, `src/api/routes/health.py`, `src/api/dependencies.py`, `src/api/middleware.py`, `tests/unit/test_app_lifecycle.py`, `tests/unit/test_health.py`.
  - Expected behavior: Tests explicitly enter FastAPI lifespan while using httpx ASGI transport; app import and health routing do not connect to PostgreSQL; injected fakes prove allocation/disposal exactly once; `/health` returns JSON `200`, unsupported methods return `405`, and correlation context does not leak across concurrent success/failure requests.
  - Logging requirements: Log request start/completion at DEBUG with safe method/path/status/duration and operational request ID, app startup/shutdown at INFO, malformed inbound correlation IDs at WARNING, and unhandled failures at ERROR. Never log bodies, authorization headers, arbitrary query values, settings, or domain identifiers as request IDs.
  - Dependencies: Tasks 2 and 6-8.

- [x] Task 10: Containerize the API, migrations, PostgreSQL, and pgvector development stack
  - Deliverable: Create a multi-stage Dockerfile pinned to an immutable Python 3.12 slim image reference, install from `uv.lock` without re-resolution, and run Uvicorn as a non-root user on port 8000. Define modern Docker Compose v2 services using a pinned PostgreSQL 17 pgvector image, one-shot Alembic migration, and API startup after migration success; use Python rather than undeclared `curl` for the API health check. Keep development credentials explicitly non-production and document that expanded `docker compose config` output is not secret-safe.
  - Files: `Dockerfile`, `.dockerignore`, `compose.yaml`, `tests/compose/test_stack.py`.
  - Expected behavior: `docker compose config --quiet` and locked image build succeed; database health precedes migration; migration exits zero before API startup; `/health` succeeds; API runs as non-root; an opt-in smoke test uses a unique project name/host port, captures redacted logs on failure, and always removes only its own volumes/orphans. Ordinary unit/integration runs never invoke Docker.
  - Logging requirements: Route logs to stdout/stderr as structured records; service lifecycle is INFO, dependency waits are DEBUG, degraded health is WARNING, and terminal startup/migration failures are ERROR. Test log capture redacts credentials and never prints expanded environment values.
  - Dependencies: Tasks 1, 8-9.

- [x] Task 11: Document and verify the foundation contract end to end
  - Deliverable: Document locked setup, environment precedence, safe test-database provisioning, local and Docker workflows, migration commands, exact test commands, architecture matrix/public facades, all eleven invariants, logging/redaction policy, seed/ID/clock derivation, LLM provenance/replay limits, and deferred simulation scope. Run each task's existing unit, property-based, typing, architecture, PostgreSQL/pgvector migration, wheel-install, and opt-in Compose checks; do not defer unfinished implementation or tests into this task.
  - Files: `README.md`, `docs/architecture.md`, `docs/configuration.md`, `docs/development.md`, existing tests from Tasks 1-10.
  - Expected behavior: A new contributor can install, configure, migrate, run, and test the foundation from documented commands. Checks prove the structural preconditions for the invariants, deep immutability/ownership, trust-stage separation, deterministic local primitives, lifecycle/health behavior, database/migration safety, pgvector availability, and isolated container startup; behavioral simulation enforcement remains explicitly deferred.
  - Logging requirements: Documentation defines event names, DEBUG/INFO/WARNING/ERROR use, correlation/provenance fields, environment control, operational-versus-domain metadata, and prohibited sensitive fields. Verification captures redacted diagnostics only on failure and adds no report artifact or unconditional runtime logging.
  - Dependencies: Tasks 1-10.

<!-- Commit checkpoint: tasks 9-11 -->

## Acceptance Criteria

- The locked Python 3.12 reference environment installs without re-resolution; wheel installation, linting, type checking, architecture checks, unit tests, and Hypothesis tests pass.
- PostgreSQL integration tests apply Alembic to an empty database, reach one head, confirm the `vector` extension, and connect through SQLAlchemy's async stack.
- Docker Compose builds and starts PostgreSQL, migrations, and FastAPI in dependency order, and `GET /health` returns a minimal successful response.
- The requested bounded packages exist with side-effect-free imports and machine-enforced dependency constraints.
- Typed contracts and architecture tests encode the structural preconditions for all eleven invariants without implementing a simulation loop or domain behavior; future simulation tasks own behavioral enforcement.
- No excluded technology or microservice boundary is introduced.
- Documentation is completed through the mandatory docs checkpoint.
