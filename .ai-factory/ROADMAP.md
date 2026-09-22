# Roadmap

## Current Milestone

### M2.5 — V1 Physical Simulation

**Status:** complete (plan `v1-physical-simulation-rules`)

Graph topology and capacities, portable items and resources, physiology and terminal death, day/night/weather/visibility, physical action rules, schema-v3 effect-complete events, autonomous tick step, persistence migration `0003`, and property/determinism proofs. Psychological fear of death remains out of scope.

**Plan:** `.ai-factory/plans/v1-physical-simulation-rules.md`

### M2 — Simulation Loop

**Status:** complete (plan `v1-feature-v1-world-engine`)

Authoritative deterministic `WorldEngine` tick loop: observe → ordered submissions → resolve, private rules, schema-versioned event export, and replay proofs.

**Plan:** `.ai-factory/plans/v1-feature-v1-world-engine.md`

### M1.5 — V1 Core Domain Model and Contracts

**Status:** complete (branch `feature/v1-core-domain-model-contracts`)

Typed objective/subjective models, closed fifteen-command trust pipeline, private world operations, immutable events, and schema-v1 serialization — still without a tick loop or behavioral resolution policy.

**Plan:** `.ai-factory/plans/v1-feature-v1-core-domain-model-contracts.md`

### M1 — V1 Project Foundation

**Status:** complete (branch `feature/v1-project-foundation`)

Establish the modular-monolith foundation: packaging, bounded packages, typed contracts, settings/logging, async DB + Alembic/pgvector bootstrap, FastAPI health API, containers, and documentation — without a simulation loop.

**Plan:** `.ai-factory/plans/v1-feature-v1-project-foundation.md`

## Next

### M3 — Cognition and Providers (complete, 2026-09-22)

**Delivered:**
- Explicit async `CognitiveLoop` + per-agent `AgentRuntime`
- Owner-scoped episodic memory, semantic beliefs, relationships, reconstructive recall
- Deterministic subjective imagination / motivation / intention
- Research FastAPI surface (`/v1` control, inspection, gated debug, WebSocket stream)
- Canonical five-agent reference scenario + V1 metric catalog assembly

**Deferred (post-V1):** LLM provider lifecycle composition in API / `compose.yaml` (factory ports exist)

**Plan:** `.ai-factory/plans/v1-complete-v1-experimental-metrics-inspection-api.md`

### M4 — Persistence and Analysis (complete, 2026-09-22)

**Persistence:** durable run manifests, event store, checkpoints, scientific evidence (`0012`), run control (`0011`), stream outbox, recovery/rehydration.

**Analysis:** fifteen V1 metric families with executable specifications, evidence-manifest revision, and experiment collection. Truth specs remain analysis-only.

**Plan:** `.ai-factory/plans/v1-complete-v1-experimental-metrics-inspection-api.md` (closes deferred M4 analysis scope)

## V1 status

V1 completion is the successful verification of plan Tasks 1–22 (Commit 6: `feat(v1): enforce end-to-end completion gates`).
