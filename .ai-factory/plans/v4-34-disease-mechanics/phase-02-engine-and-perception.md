# Phase 2: Engine lifecycle and agent-visible cues

Plan: [index.md](index.md)  
Tasks: 3–4  
Depends on: Phase 1 / Tasks 1–2

## Objective

Make the fictional condition progress only in the engine tick transaction; give owners only symptom cues and existing evidence.

## Current-Code Evidence

| Path | Symbols / sections | Why it matters |
| --- | --- | --- |
| `src/simulation/engine.py` | `_prepare_tick_candidate`, `observe`, detached agent observation, lifespan death | Candidate integration, final order, visibility and cursor parity |
| `src/simulation/service.py` | Durable tick commit around line 414 | Persists before publishing the candidate |
| `src/world/_physical.py`, `src/world/_travel.py` | Autonomous step, `Died`, `_append_corpse_custody`, death-related journey cancellation | Reuse terminal consequences and cleanup |
| `src/world/_perception.py` | Self projection and generic occurrence audience assignment | Private transitions must be rejected before audience classification |
| `src/world/observations.py`, `src/simulation/serialization.py` | `ObservedSelf`, `observed_self_from_body`, `_encode_observed_self`, `_decode_observed_self` | Exact additive self-only cue and off-path wire equality |

## Files to Change

| Path | Action | Responsibility |
| --- | --- | --- |
| `src/world/_disease.py` | Modify | Pure simultaneous transition pass; emits effective changes only |
| `src/simulation/engine.py`, `src/simulation/bootstrap.py` | Modify | Initial founder state, seeded draws, candidate lifecycle and restore parity |
| `src/world/events.py`, `src/world/effects.py`, `src/world/_transitions.py`, `src/world/_physical.py` | Modify | Internal transition detail, stable effect ordering, reuse death handling |
| `src/world/_perception.py`, `src/world/observations.py`, `src/simulation/serialization.py` | Modify | Safe cue projection, exact optional field, occurrence suppression |
| `tests/unit/test_disease_engine.py`, `tests/unit/test_disease_perception.py`, `tests/architecture/test_disease_boundaries.py` | Create | Mechanics, perception noninterference, and imports |

## Task 3: Advance the hidden lifecycle in one candidate pass

### Intent

Run the fictional state machine on an empty or populated action tick without creating a new command, intervention, environmental mechanism, or agent policy.

### Implementation Steps

1. Apply founder latent assignments in `simulation.bootstrap` before the first observation and persist them in the initial checkpoint. Nonfounders enter susceptible. In the engine's detached candidate, insert the pass after normal autonomous physical effects and before lifecycle admission/death and journey cleanup. Start from a frozen disease view at the beginning of the pass; never read a row written by the current pass as a source. Reconcile rows of bodies that die later in the ordinary lifecycle pass before boundary validation. Do not copy rows onto new entrants.
2. For a start-of-tick settled living agent that survives normal physics, define eligible contact as sharing the same settled location with another such agent both at tick start and at the pass, with each participant still in their own starting location. Exclude agents in ongoing journeys at either boundary and same-tick entrants. Group by location to avoid a population-wide pair scan. A susceptible agent with at least one active participant in its group has one eligible exposure opportunity. Exposure and fictional transmission each use one independent Boolean draw per target/tick, in that order; multiple active participants do not add trials. No transient path or hidden-contact evidence is emitted. Stable iteration uses sorted entity IDs.
3. In engine composition pass the pure rule a draw callback backed by `simulation.randomness.derive_stream_seed` and `create_rng`. Use `StreamScope("disease-mechanics.v1", (str(tick), entity_id.value, draw_kind))`, where `draw_kind` is one of `exposure`, `transmission`, `symptom`, `terminal`. Compare the resulting private generator's `randrange(1000)` with each configured milli threshold using `<`; endpoints are exact. Do not include run ID, iteration position, the global RNG, time, or a shared mutable stream. The same inputs produce the same draws after restore and in paired arms. Disabled runs never call the draw path.
4. At resolution of tick `t`, `S → L` makes the latent deadline `t + latent_ticks`. A due latent row becomes active and sets its terminal deadline `t + active_ticks`; sample its symptom bit once at that transition. A start-of-pass active row remains eligible as a contact source through its terminal boundary, then draws once for mortality or else recovers. Recovery yields permanently immune or immediately susceptible at the next pass, according to the run-level Boolean; never re-expose a row in the same pass in which it recovers. A newly activated row cannot transfer until the next pass. Normal-physics deaths take precedence; disease mortality comes before lifespan mortality. Remove disease rows for dead bodies; never revive a body.
5. Apply terminal mortality with the existing death conventions (`Health(0)`, `LifeStatus.DEAD`, one `Died`, optional corpse custody, ordinary journey cleanup and runtime retirement). The usual lifespan pass skips bodies already dead. Redact the version-gated death cause from presentation and agent occurrence views. After lifecycle and journey cleanup, compute the sorted union of start and final disease-row keys and queue one private net before/after effect per changed body. A newly acquired row followed by same-tick ordinary death has no net effect; a pre-existing row on a dead body is removed once. Append internal effects after all ordinary events (including death and custody), with deterministic system IDs, so hidden-only changes do not shift the sequence numbers of ordinary events in that tick.

### Contracts / evidence

- `WorldEngine` is the only commit authority. This model is a single fictional token with arbitrary tick timings; no real pathogen, calibration, medical advice, or optimization surface.
- Log at DEBUG only channel activation, tick progress and safe validation reason codes, never participant IDs paired with condition, transition outcomes, contact pairs, probabilities sampled, or event bodies. Invalid state is an invariant error, not an opportunity to silently heal state.

### Tests, acceptance, and verification

- `tests/unit/test_disease_engine.py`: disabled inertness; empty tick; 0/1000 trials; multiple-source deduplication; remote/transit/arrival/newborn exclusion; same-pass no chain; exact onset and terminal ticks; both immunity branches; one death, custody and journey cleanup; physics death precedence; later lifespan death that removes an existing row or cancels a new row; unchanged ordinary-event order when only hidden rows differ. Check that abandoning the detached candidate leaves live state unchanged; durable failure is proved in Task 5.
- Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_disease_engine.py tests/unit/test_regional_travel_lifecycle.py tests/unit/test_death_corpse_custody.py -q`. Acceptance: net effects are stable under map permutation and existing death pipelines remain intact.

## Task 4: Project symptom cues without exposing infection

### Intent

Let agents perceive a coarse subjective-accessible symptom, and ordinary visible co-presence and events, without an infection or immunity query.

### Implementation Steps

1. Add one closed optional `ObservedSelf.symptom_cue` with the sole present token `unwell`. Derive it only for the living owner with a current positive cue; absent for everyone else, including asymptomatic active, latent, immune and disease-off. Keep existing `VisibleBody`, status/role semantics, `Observation` top-level keys, and prompt/memory schemas unchanged. Contact perception uses existing visible co-presence and delivered events, not an exposure detector or hypothetical contact from disease rows.
2. Wire the same projection through live and restored agent-visible observation. Add strict optional encoding/decoding on `ObservedSelf` only; omit the field rather than emitting null. Preserve source hierarchy, remembered observations and observation stability within a tick. Keep `src/api/schemas.py:AgentVisibleOut` metadata-only and unchanged; omit the cue from observer frames.
3. Reject disease transition events before generic occurrence audience selection, even if an objective event has a local actor or effect entity. The ordinary projected death has no disease cause or auxiliary disease-transition ID. Do not bypass standard observer filtering (see Task 6), clone peers' symptoms, expose private event references, or add agent-accessible status methods.

### Contracts / evidence

- The request distinguishes symptom/contact/event perception from objective infection knowledge; `.ai-factory/ARCHITECTURE.md` defines the one-owner observation boundary. No false claim that cue absence disproves disease. Log only projection validation reason codes, not cue values or the raw observation.

### Tests, acceptance, and verification

- In `tests/unit/test_disease_perception.py`, compare same physical state with differing hidden states that generate no cue: identical agent-visible wire values and unchanged non-owner projections. Compare cue on/off, owner/nearby/remote, repeated calls, historical/live projections, and internal event with intentionally local context. Verify the ordinary death occurrence has no diagnostic payload. In `tests/architecture/test_disease_boundaries.py`, forbid importing private state from cognition, memory, LLM, observer and clients.
- Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_disease_perception.py tests/unit/test_world_perception_isolation.py tests/unit/test_perception_event_isolation.py tests/architecture/test_disease_boundaries.py -q`. Acceptance: the only new readable signal is optional owner `unwell`, and off-path observation bytes are unchanged.

## Phase Risks and Mitigations

- Early writes can cause order-dependent chains; use the frozen pass input and sorted stable keys.
- Filtering only payloads can reveal event existence; the audience boundary drops the entire internal transition.

## Phase Completion Checklist

- Verify Tasks 3–4 and update only `index.md` progress after each success.
