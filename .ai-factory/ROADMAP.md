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

### M6 — Remaining V2 Capability Flags (in progress)

**Goal:** Own the remaining default-off `V2CapabilityFlags` beyond short-term emotion, each with fail-closed allowlist ownership, V1 regression gates green when flags-off, and no LLM→world shortcuts.

**Started:** `extended_self_model` is owned and default off. When enabled it forms history-derived, revisable self-beliefs (abilities, weaknesses, commitments, and the other closed identity aspects). It is not a person class, a persisted self-model row, or a second belief store. Experiment H and `identity_dynamics@1` stay off the V1 regression gate.

`predictive_world_model` is owned and default off (2026-09-26). When enabled, each agent keeps a private causal world model updated from its own observations and reconstructed memories, and matching hypotheses bias imagination and planning. Off is a passthrough: no hypotheses, no command bias, no audit. Confidence is subjective support, not an engine probability. Hypotheses are not semantic beliefs. Experiment I and `causal_world_model@1` stay analysis-only and off the V1 regression gate.

`short_term_emotional_state` was already owned in M5.3.

`advanced_social_inference` is owned and default off. When enabled, each agent keeps a private first-order model of other agents from its own observations and uses it to bias social action. Off is a passthrough: no hypotheses, no command bias, no audit. The model can be wrong. Experiment L and `theory_of_mind@1` stay analysis-only and off the V1 regression gate. One agent does not receive another agent's private cognition.

Named cognitive architecture variants (`agents.cognition.architectures`, Experiment AC) compose owned flags and cognition modes as experiment presets without new flag slots or a runner `architecture_id` schema key (2026-10-03).

**Still unimplemented:** `multi_hop_testimony_tracking`. Enabling it still fails closed with `capability_unimplemented`.

**Next plan:** own `multi_hop_testimony_tracking` (still fails closed with `capability_unimplemented`).

`.ai-factory/plans/v2-physical-external-artifacts.md` is implemented. It adds WorldEngine-owned information artifacts (mark/sign/note/map/record/memorial), opt-in `ArtifactInterpretationMode` on `runner-config-v19`, replay-v8 / codec v5 when artifacts are active, Experiment Z, and `external_artifact_memory@1`. Meaning stays subjective; scene memory does not auto-download marks. No capability flag. M6 stays open for `multi_hop_testimony_tracking`.

`.ai-factory/plans/v2-emergent-semantic-naming.md` is implemented. It adds an opt-in owner-scoped terminology ledger on `runner-config-v20`, Experiment AA, and `emergent_semantic_naming@1`. Agents invent, adopt, compete over, merge, shift, and forget bounded labels without a world dictionary or natural-language path. Digest-only seeds never parse location/exit names. Researcher overlays stay additive under `subjective_debug`. No capability flag. M6 stays open for `multi_hop_testimony_tracking`.

`.ai-factory/plans/v2-long-lived-cultural-narratives.md` is implemented. It adds an opt-in owner-scoped narrative lineage ledger on `runner-config-v21`, Experiment AB, and `cultural_narrative_lineage@1`. Agents track recurring story variants with branch/merge lineage and gated semantic-belief uplift — without hard-coded Myth objects or automatic society-wide influence. No capability flag. M6 stays open for `multi_hop_testimony_tracking`.

`.ai-factory/plans/v2-godot-observer-mechanics-viz.md` is implemented. It expands the read-only Godot observer for V2 physical/social/communicative/cultural presentation (structures, production events, evidence-class overlays, metric catalog discovery, per-event strategy audit, SUBJECTIVE narrative-ledger hops, perspective limits). No capability flag, no protocol rename, no WorldEngine semantics change. M6 stays open for `multi_hop_testimony_tracking`.

`.ai-factory/plans/v2-godot-causal-debugger-inspector.md` is implemented (2026-10-04). It upgrades the Godot research debugger to a compact Why? inspector (presentation labels, artifact-kind chrome, Seek vs Provenance, return stack) over the already-shipped server causal debugger. No capability flag, no wire/schema bump, no causal assembly in Godot. M6 stays open for `multi_hop_testimony_tracking`.

`.ai-factory/plans/v2-repeated-social-conventions.md` is implemented. It adds an opt-in owner-scoped convention ledger on `runner-config-v18`, Experiment Y, and `persistent_social_conventions@1`. Agents learn habitual "we usually do X in situation Y" beliefs via observation, memory, and communication — without predefined tradition scripts. Ritual/tradition labels stay analysis-only until agents conceptualize them. No capability flag. M6 stays open for `multi_hop_testimony_tracking`.

`.ai-factory/plans/v2-computational-cognitive-budgets.md` is implemented. It adds default-off `CognitiveBudgetMode` / `TickBudgetLedger` on `runner-config-v22`, Experiment AD (`ad-low-cost` / `ad-high-cost`), and `cognitive_budget@1`. Per-tick LLM/token/branch/depth/memory/ToM/reflection/timeout caps degrade gracefully without skipping the closed command. No capability flag. M6 stays open for `multi_hop_testimony_tracking`.

`.ai-factory/plans/v2-reproducible-experiment-matrices.md` is implemented. It adds `experiment-matrix-v1` factor grids, filesystem resume manifests, process-local `MatrixBatchRunner`, `matrix-aggregate-v1`, and the `research_runner` / `palimpsest-matrix` CLI (no HTTP). Composes already-owned modes/flags only; does not own `multi_hop_testimony_tracking`. M6 stays open for that flag.

`.ai-factory/plans/v2-expanded-analysis-beyond-v1-metrics.md` is implemented (2026-10-03). It expands analysis-only phenomenon indicator panels, four new catalog families (count 39), survival cohort contrast sibling docs, optional cell metric sidecars, and `matrix-metric-summary-v1` / `--metric-summary` without owning `multi_hop_testimony_tracking`. M6 stays open for that flag.

`.ai-factory/plans/v2-simulation-branching.md` is implemented (2026-10-04). It adds research-only deterministic forks (`ResearchIntervention`, Alembic `0015` `simulation_branches`, `/v1/.../branches`, observer lineage metadata) over replay checkpoints without rewriting parent history or adding a capability flag. Agent `CounterfactualScenario` stays separate. M6 stays open for `multi_hop_testimony_tracking`.

`.ai-factory/plans/v2-llm-recording-replay-layer.md` is implemented (2026-10-04). It replaces the stub `recorded` → fake fallback with a real `llm.recording` record/cache/replay layer (`RecordingLLMProvider`, filesystem store, composition-only `RecordingStoreSettings`). Expands `RecordingPolicy` with `record`/`cache`/`replay` (legacy `recorded` aliases to `replay`). No capability flag. M6 stays open for `multi_hop_testimony_tracking`.

`.ai-factory/plans/v2-emergent-social-norms.md` is implemented. It adds an opt-in owner-scoped social-norm ledger on `runner-config-v17`, Experiment X, and `emergent_social_norms@1`. A norm is a private belief inferred from repeated observations. It is not a `WorldEngine` rule, and it does not own a capability flag. Opt-in group formation already landed on `runner-config-v16`. Territorial claims already landed as `runner-config-v15`, Experiment V, and `spatial_control@1`.

**Out of scope until planned:** free-form affect narration, personality trait systems, HTTP debug UI for emotion, collapsing emotion+drives+goals into one reward scalar.

**Plans:** `.ai-factory/plans/v2-emergent-dynamic-identity.md` (owns `extended_self_model` only). `.ai-factory/plans/v2-learned-causal-worldmodel.md` (owns `predictive_world_model` only). `.ai-factory/plans/v2-first-order-theory-of-mind.md` (owns `advanced_social_inference` only). Opt-in work that did not claim a flag already shipped as M5.4 and M5.5. `.ai-factory/plans/v2-subjective-territorial-claims.md` (no flag; `runner-config-v15`). `.ai-factory/plans/v2-emergent-group-formation.md` (implemented 2026-10-02; no flag; `runner-config-v16`). `.ai-factory/plans/v2-emergent-social-norms.md` (implemented 2026-10-02; no flag; `runner-config-v17`). `.ai-factory/plans/v2-repeated-social-conventions.md` (implemented 2026-10-03; no flag; `runner-config-v18`). `.ai-factory/plans/v2-physical-external-artifacts.md` (implemented 2026-10-03; no flag; `runner-config-v19`). `.ai-factory/plans/v2-emergent-semantic-naming.md` (implemented 2026-10-03; no flag; `runner-config-v20`). `.ai-factory/plans/v2-long-lived-cultural-narratives.md` (implemented 2026-10-03; no flag; `runner-config-v21`). `.ai-factory/plans/v2-computational-cognitive-budgets.md` (implemented 2026-10-03; no flag; `runner-config-v22`). `.ai-factory/plans/v2-godot-observer-mechanics-viz.md` (implemented 2026-10-03; no flag; presentation-only).

## V1 status

V1 completion is the successful verification of plan Tasks 1–22 (Commit 6: `feat(v1): enforce end-to-end completion gates`).

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

## V2 delivered

### M5 — V2 Architectural Scaffolding (complete, 2026-09-22)

Version compatibility matrix, `runner-config-v3+` with default-off reserved capability flags (fail closed until owned), V1 regression gates, and downstream V2 plan contract — without new social/cognitive behavior in the scaffolding plan.

**Plan:** `.ai-factory/plans/v2-architecture-evolution.md`

### M5.1 — Cognitive Execution Trace (complete, 2026-09-23)

Optional, default-off `CognitionTraceSpec` / `runner-config-v4`, non-authoritative durable stage traces (Alembic `0013`), ports and null sink — outside the objective fold; tracing-off trajectories unchanged.

**Plan:** `.ai-factory/plans/v2-cognitive-execution-trace.md`

### M5.2 — Hierarchical Long-Term Goal Management (complete, 2026-09-24)

Owner-scoped hierarchical `GoalBoard` / `goals.v1` GoalManager stage, lifecycle transitions, live goal application, conflict scenarios, and cognition-trace goal projection — not a capability flag.

**Plan:** `.ai-factory/plans/v2-hierarchical-long-term-goal-management.md`

### M5.3 — Short-Term Emotional State (complete, 2026-09-24)

Owned flag `V2CapabilityFlags.short_term_emotional_state` (default off), closed-catalog `AgentEmotionalState` / `emotion.v1` stage, runtime carry, deterministic influence hooks, checkpoint codecs, live trace projection, and V1 regression under flags-off.

**Plan:** `.ai-factory/plans/v2-short-term-emotional-state.md`

### M5.4 — Reconstructive Memory Dynamics (complete, 2026-09-25)

Opt-in `MemoryMode.RECONSTRUCTIVE_V2` for cue-dependent recall, interference, source confusion, and semanticization. Audits stay analysis-only (`memory_dynamics@1`). The extra Experiment A arm stays off the V1 regression gate. This is a cognition mode, not a capability flag.

**Plan:** `.ai-factory/plans/v2-reconstructive-memory-dynamics.md`

### M5.5 — Offline Memory Consolidation During Sleep (complete, 2026-09-25)

Opt-in `ConsolidationMode` (default `DISABLED`) reorganizes owner-scoped traces when the effective command is `Sleep`: strengthen, merge, soft-forget, and revise beliefs, relationships, and goals from existing subjective evidence. Default configs stay `runner-config-v4`; `runner-config-v5` is written only when a mode is enabled. Experiment F and `offline_consolidation@1` stay off the V1 regression gate. This is a cognition mode, not a capability flag.

**Plan:** `.ai-factory/plans/v2-offline-sleep-memory-consolidation.md`
