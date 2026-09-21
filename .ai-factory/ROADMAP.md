# Roadmap

## Current Milestone

### M2.5 — V1 Physical Simulation

**Status:** complete (plan `v1-physical-simulation-rules`)

Graph topology and capacities, portable items and resources, physiology and terminal death, day/night/weather/visibility, physical action rules, schema-v3 effect-complete events, autonomous tick step, persistence migration `0003`, and property/determinism proofs. Psychological fear of death remains out of scope.

**Plan:** `.ai-factory/plans/v1-physical-simulation-rules.md`

### M2 — Simulation Loop

**Status:** complete (plan `feature-v1-world-engine`)

Authoritative deterministic `WorldEngine` tick loop: observe → ordered submissions → resolve, private rules, schema-versioned event export, and replay proofs.

**Plan:** `.ai-factory/plans/feature-v1-world-engine.md`

### M1.5 — V1 Core Domain Model and Contracts

**Status:** complete (branch `feature/v1-core-domain-model-contracts`)

Typed objective/subjective models, closed fifteen-command trust pipeline, private world operations, immutable events, and schema-v1 serialization — still without a tick loop or behavioral resolution policy.

**Plan:** `.ai-factory/plans/feature-v1-core-domain-model-contracts.md`

### M1 — V1 Project Foundation

**Status:** complete (branch `feature/v1-project-foundation`)

Establish the modular-monolith foundation: packaging, bounded packages, typed contracts, settings/logging, async DB + Alembic/pgvector bootstrap, FastAPI health API, containers, and documentation — without a simulation loop.

**Plan:** `.ai-factory/plans/feature-v1-project-foundation.md`

## Next

### M3 — Cognition and Providers (in progress)

**Delivered (2026-09-21):**
- Explicit async `CognitiveLoop` + per-agent `AgentRuntime` (plan `v1-agent-runtime-cognitive-loop`)
- Owner-scoped episodic `MemoryService`, structured `MemoryTrace`, deferred access apply, Alembic `0005` / SQLAlchemy adapter (plan `v1-episodic-memory-traces`)

**Still open:**
- Richer production cognition policies beyond V1 placeholders
- LLM provider lifecycle composition in API / `compose.yaml` (factory ports exist)

### M4 — Persistence and Analysis (persistence complete; analysis deferred)

**Persistence (complete, 2026-09-19):** plan `feature-event-sourcing-persistence-replay` — durable run manifests, append-only PostgreSQL event store, checkpoints, `PersistentSimulationService`, and `ReplayService` with deterministic reconstruction. Extended by M2.5 physical schema-v3 / migration `0003`. Experiment metadata is queryable; analysis metrics over exports are not claimed complete.

**Still open:** read-only analysis metrics over immutable exports.
