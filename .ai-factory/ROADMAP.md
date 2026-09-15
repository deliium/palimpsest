# Roadmap

## Current Milestone

### M1 — V1 Project Foundation

**Status:** complete (branch `feature/v1-project-foundation`)

Establish the modular-monolith foundation: packaging, bounded packages, typed contracts, settings/logging, async DB + Alembic/pgvector bootstrap, FastAPI health API, containers, and documentation — without a simulation loop.

**Plan:** `.ai-factory/plans/feature-v1-project-foundation.md`

### M1.5 — V1 Core Domain Model and Contracts

**Status:** complete (branch `feature/v1-core-domain-model-contracts`)

Typed objective/subjective models, closed fifteen-command trust pipeline, private world operations, immutable events, and schema-v1 serialization — still without a tick loop or behavioral resolution policy.

**Plan:** `.ai-factory/plans/feature-v1-core-domain-model-contracts.md`

## Next (deferred)

### M2 — Simulation Loop (not started)

Tick loop, action resolution, perception, and behavioral enforcement of invariants (builds on V1 contracts).

### M3 — Cognition and Providers (not started)

Concrete cognition policies and production LLM provider adapters behind existing ports.

### M4 — Persistence and Analysis (not started)

Domain schemas beyond pgvector bootstrap; read-only analysis metrics over immutable exports.
