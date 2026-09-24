# Reconstructive memory

[← Cognition and agent runtime](cognition-runtime.md) · [Back to README](../README.md) · [Next Page →](llm-providers.md)

Downstream cognition consumes `ReconstructedMemory` episodes as subjective experience evidence for imagination and risk appraisal; ranked source traces remain scientific evidence only. Reconstructions may be inaccurate — different remembered concepts can change subjective risk without changing world truth.

## Memory modes (experiment treatments)

| `MemoryMode` | Behavior |
| --- | --- |
| `REFERENCE` | Exact/reference retrieval (`ReferenceMemoryRetriever`) |
| `RECONSTRUCTIVE` (default) | Frozen V1 merge-recall + optional reconsolidation |
| `RECONSTRUCTIVE_V2` | Opt-in dynamics: cue competition, interference, decay, source confusion, testing effects, semanticization |

V2 is selected by injecting `MemoryRecallRequest.dynamics_policy` (`memory-dynamics-v1` defaults). When `dynamics_policy is None`, the V1 path stays bit-identical. Soft-forget remains the only deactivation path — V2 never hard-deletes by age.

**Agent vs audit split:** agent-facing `ReconstructedMemory` / `RetrievedMemoryContext` never carry `RecallAuditRecord`. True provenance, competitors, and distortion codes live on `MemoryRecallResult.audits` only and export into `MemoryDynamicsReport` for metrics.

**Emotion × V2 ordering:** dynamics + audit complete inside `MemoryService.recall` first; optional `apply_*_emotion_bias` may re-rank agent-visible hits afterward. Audit `selected_ids` are pre-emotion.

## Pipeline

```text
MemoryRecallRequest (+ optional dynamics_policy)
→ owner-scoped retrieve
→ RecallEvidence
→ V1 DeterministicMemoryReconstructor  OR  V2 dynamics reconstruct
→ ReconstructedMemory (+ optional ReconsolidationIntent / pending semanticization)
→ AgentRuntime.apply (deferred, atomic with access receipts)
```

| Type | Role |
| --- | --- |
| `MemoryRecallRequest` | Composes `MemoryRetrieveRequest` + policy, beliefs, recall context, optional derived ID, optional `dynamics_policy` |
| `RecallEvidence` | Bounded canonical DTO: ranked sources, beliefs, context — **no** `WorldEvent` |
| `MemoryReconstructor` | Protocol: `reconstruct(evidence) -> ReconstructedMemory` |
| `ReconstructedMemory` | Subjective episode (narrative + structured fragments + provenance metadata) |
| `ReconsolidationIntent` | Deferred plan: append-only record, source edges, optional derived `MemoryTrace` |
| `RecallAuditRecord` | Experiment-only V2 audit (IDs/codes/counts); never on agent context |
| `MemoryRecallResult` | Reconstructions, evidence, pending accesses, optional reconsolidation, optional audits |

Opaque `EventId` may appear as `observed_source_id` correlation only. Memory, agents, cognition, and reconstruction APIs never accept or dereference `WorldEvent`.

## Subjective semantics

- Reconstruction may omit, blend, reinterpret, or invent details relative to sources.
- Output is never world authority, an objective event, a trusted belief revision, or an engine command without normal cognition → admission stages.
- Owner/run scope is enforced on every input and output; foreign-owner evidence is rejected.
- Empty retrieved sources yield no reconstruction (no invented episode from beliefs alone in the deterministic path).

## Policy composition

| Component | Location | Behavior |
| --- | --- | --- |
| `MemoryReconstructionPolicy` | `memory` | Versioned: age semantics, `allow_provider`, `fallback_mode`, `reconsolidate`, caps, `ancestry_dedup`, `generation_weight` |
| `DeterministicMemoryReconstructor` | `memory` | Default: rank-weighted confidence/salience; merge concepts/entities/relations/context in source-rank order; no free-form invention |
| `LLMMemoryReconstructor` | `agents.cognition` | Maps evidence → `LLMRequest`; prompt `llm/prompts/reconstructive_memory/v1/`; translates `ReconstructedMemoryCandidate` only after semantic validation |
| `ReconstructionFallbackMode` | `memory` | `deterministic` (default) or `reject` on provider/validation failure |
| Cancellation | both | `CancelledError` propagates; no partial reconsolidation write |

Offline / no-provider: keep `allow_provider=False` (cognition default) or omit the LLM adapter — deterministic reconstruction only.

## Exact structured vs semantic validation

| Gate | What it proves | What it does **not** prove |
| --- | --- | --- |
| Exact structured (`StructuredOutput` / `ReconstructedMemoryCandidate`) | Shape, types, bounded fields | Truth, ownership, authority, source membership |
| Domain construction (`ReconstructedMemory.__post_init__`) | Bounded narrative/fragments, unit-interval scores, non-empty sources | Agreement with evidence |
| `validate_reconstructed_memory(reconstructed, evidence=...)` | Owner/ID/policy/tick/generation match; every `source_memory_id` ∈ evidence; narrative length ≤ policy | Objective correctness |

Fail-closed: semantic rejection triggers configured fallback (or reject). Never log candidate bodies.

## Recall inputs

All inputs are typed, bounded, owner-safe, and policy-visible (no hidden globals).

| Input | Carrier | Notes |
| --- | --- | --- |
| Retrieved traces | `RecallSourceEvidence` | Rank, score, fragments, ages, generation, provenance kind, opaque `observed_source_id` |
| Current beliefs | `MemoryRecallRequest.beliefs` | Owner-scoped snapshot; capped by `max_beliefs` |
| Current context | `MemoryRecallContext` | Location, tags, related entities |
| Emotional significance | `MemoryRecallContext.emotional_significance` + per-source `emotional_salience` | Unit interval; **V1 per-trace property**. Live V2 short-term `AgentEmotionalState` (capability-flagged) may bias retrieval/reconstruction ranking without mutating stored salience — see [Cognition runtime](cognition-runtime.md#short-term-emotional-state-v2-owned-flag). |
| Social significance | `MemoryRecallContext.social_significance` | Unit interval |
| Episode / storage age | `episode_age_ticks` / `storage_age_ticks` | Explicit logical ticks via `MemoryAgeSemantics` |
| Source confidence | `RecallSourceEvidence.source_confidence` | Unit interval |
| Stable IDs | `reconstruction_id`, optional `derived_memory_id` | Caller-supplied; required when `reconsolidate=True` |

## Non-destructive reconsolidation

- Inserts `ReconstructionRecord` + ordered reconstruction source edges + optional derived `MemoryTrace` + derivation edges in one `MemoryMutationBatch`.
- **Never** overwrites, deletes, soft-forgets, or deactivates source traces as a side effect of reconsolidation.
- `MemoryLineage.supersedes_memory_id` is a principal predecessor for compatibility — not permission to replace the parent.
- Dense generation: derived generation = `1 + max(source generations)`.
- Idempotent retries; conflicts roll back the entire batch (no partial edges).
- `AgentRuntime` applies pending reconsolidation only after the full cognitive loop succeeds, together with access receipts. Cognition failure leaves memory unchanged.

## Lineage traversal

| Artifact | Contents |
| --- | --- |
| `MemoryLineage` | `source_memory_ids`, optional `reconstruction_id`, `supersedes_memory_id`, `generation` |
| `memory_reconstruction_sources` | Ordered sources per reconstruction |
| `memory_derivation_sources` | Derived trace → direct parents + producing reconstruction |
| Analysis chains | `objective event? → root trace → reconstruction → derived → …` via opaque correlation |

`collect_ancestry_ids` walks derivation edges for scoring / ancestry de-duplication. Cycles, self-links, dangling, and cross-owner/cross-run references are rejected at apply time.

## Retrieval weighting and decay

Configured on `MemoryScoringPolicy` / `MemoryRetentionPolicy` / reconstruction policy — defaults preserve prior behavior unless callers opt in.

| Knob | Effect |
| --- | --- |
| Logical-age decay | Recency from `STORAGE` (`created_tick`) or `EPISODE` (`source_tick`) semantics |
| `generation_influence` / `generation_weight` | Prefer newer lineage generations when enabled |
| `ancestry_dedup` | De-duplicate ancestors in ranking without hiding old traces from audit |
| Retention half-life | Soft-forget via `MemoryRetentionPolicy` (explicit ticks; separate from reconsolidation) |

Tie-break remains `score DESC, created_tick DESC, memory_id ASC`.

## Persistence (Alembic `0006` / `0007` / `0008`)

Reconstruction provenance tables (`0006`) stay under `SUBJECTIVE_MEMORY_TABLES`. Semantic belief and directed relationship tables (`0007`) live under `SUBJECTIVE_AGENT_TABLES`. Revision `0008` adds communicated transmission metadata on `memory_traces` and applied testimony factors on `semantic_belief_evidence`. Belief evidence references owned `memory_traces` only — never `world_events`.

| Table | Mutability |
| --- | --- |
| `memory_reconstructions` | Append-only |
| `memory_reconstruction_sources` | Append-only |
| `memory_derivation_sources` | Append-only (includes backfill from valid `supersedes_memory_id`) |
| Fragment tables (`memory_concepts`, …) | Append-only |
| `memory_traces` | **Selective**: content immutable; access counts / explicit forgetting still mutable |

All subjective tables stay **outside** `AUTHORITATIVE_TABLES` and objective replay. No objective-event FK from memory. Transaction: reconstruct + edges + optional derived write + access receipts commit atomically or not at all.

## Experiment-only objective comparison

`analysis.MemoryDriftAnalysisService` independently reads:

1. Subjective evidence (`MemoryEvidenceSource`: traces, reconstructions, derivation edges)
2. Immutable objective events (`ObjectiveEventSource`)

Join is **after** reconstruction, by run/owner + opaque `observed_source_id`. Missing links → `unknown` / unlinked — never inferred into agents or reconstructors.

| Metric surface | Contents |
| --- | --- |
| `DriftDelta` | Retained / lost / added concepts, entities, relations, context tags; location change; confidence/salience deltas; provenance continuity; canonical equality; unsupported/contradicted facts |
| `MemoryDriftReport` | Chains, per-step `DriftStep`, cumulative deltas, linked/unlinked/absent counts; `DRIFT_METRIC_VERSION` / `EVENT_FACT_PROJECTOR_VERSION` |

Import-linter allows `analysis → memory` (read-only contracts). Agents, cognition, `MemoryService`, and reconstructors must not import event stores, replay, or private world authority.

## Replay limitations

- Objective event hashes, revisions, continuation eligibility, and `ReplayService` output are independent of subjective recall/reconsolidation.
- Live external LLM calls are **not** bit-for-bit replayable without recorded validated outputs or deterministic stubs/fakes.
- Persisted reconstruction evidence and deterministic reconstructors support reproducible experiment analysis.

## Logging (metadata only)

Control verbosity with `PALIMPSEST_LOG_LEVEL`. Payloads are prohibited everywhere below.

### Safe event names

| Area | Events (examples) |
| --- | --- |
| Recall orchestration | `memory_recall_start`, `memory_recall_complete`, `memory_recall_empty_sources`, `memory_recall_evidence_rejected`, `memory_recall_reconsolidation_intent`, `memory_recall_invalid`, `memory_recall_ownership` |
| LLM reconstruction | `memory_llm_reconstruction_skipped`, `_start`, `_complete`, `_fallback`, `_rejected`, `_cancelled`, `_terminal` |
| Cognition mapping | `memory_recall_mapped`, `memory_recall_foreign_owner` |
| Apply / runtime | `memory_reconsolidation_committed`, `memory_reconsolidation_idempotent`, `runtime_reconsolidation_committed`, `runtime_memory_apply_*` |
| Analysis | `memory_drift_analysis_start`, `_complete`, `_metrics`, `_read_failed`, `memory_drift_unlinked_source`, `memory_drift_provenance_break` |
| Migration `0006` | `memory_reconstruction_migration_start`, `memory_reconstruction_backfill_complete` |

### Allowlist

IDs (run / owner / reconstruction / request / invocation), logical tick, policy / prompt / schema / model versions, counts, generation, `used_provider` / `fallback_used`, durations, stable reason/error codes.

### Prohibited

Narratives, beliefs, memory fragments, embeddings, communications, prompts, schemas, provider request/response bodies, objective event payloads, SQL parameters, DSNs, credentials, exception text carrying payloads.

## Tests (targeted)

```bash
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_memory_reconstruction.py \
  tests/unit/test_memory_llm_reconstruction.py \
  tests/unit/test_memory_reconstruction_drift.py \
  tests/unit/test_memory_drift_analysis.py \
  tests/unit/test_reconstruction_analysis_service.py \
  tests/architecture/test_analysis_isolation.py \
  tests/architecture/test_memory_isolation.py -q

PALIMPSEST_TEST_DATABASE_URL=... uv run --frozen --python 3.12.14 pytest \
  -m integration tests/integration/test_migrations.py \
  tests/integration/test_episodic_memory_pgvector.py \
  tests/integration/test_memory_concurrency.py -q
```

## See Also

- [Cognition and agent runtime](cognition-runtime.md) — memory stage and deferred apply
- [Persistence](persistence.md) — `0006` tables and selective immutability
- [LLM providers](llm-providers.md) — structured provider boundary used by LLM reconstruction
- [Architecture](architecture.md) — package imports and objective/subjective boundary
