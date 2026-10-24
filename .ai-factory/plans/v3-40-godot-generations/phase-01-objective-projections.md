# Phase 1: Cursor-correct demographic projections

Plan: [index.md](index.md)  
Tasks: 1–3  
Depends on: none

## Objective

Expose demographic facts and generation markers without widening existing observer frame schemas, changing simulation behavior, or requiring lineage capture for ordinary population inspection.

## Current-Code Evidence

| Path | Symbols / section | Why it matters |
|---|---|---|
| `src/world/lifecycle.py` | `AgentLifecycleRecord`, `chronological_age` | Entry tick, stage, dependency, generation and cohort already exist; entry is not biological birth. |
| `src/simulation/engine.py` | `detached_objective_facts` | Sole trusted extraction seam; currently omits lifecycle metadata. |
| `src/simulation/observer_facts.py` | `ObjectiveFacts`, `ObjectiveScene`, `_freeze_facts`, `scene_from_snapshot` | Detached scene transport; no engine ownership. |
| `src/simulation/replay.py` | `scene_at_tick`, `scene_through_event` | Both copy facts after objective replay and release the restored engine. Complete event prefix advances the clock; partial prefix does not. |
| `src/simulation/replay.py`, `src/simulation/engine.py` | `ReplayService.replay`, `restore_from_snapshot`, `_apply_event_prefix` | Current scene replay omits required lifecycle restore context; world event folding does not rebuild engine-owned lifecycle records/registrations. Copying facts alone is insufficient. |
| `src/simulation/generational_progress.py` | `build_population_progress` | Exact totals/cohort/generation fold; rejects missing body bindings. |
| `src/api/observer_service.py` | `state`, `_history`, `_history_through_event` | Existing cursor resolution and error mapping. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/simulation/observer_facts.py` | modify | Add optional detached lifecycle records; preserve absent versus active-empty. |
| `src/simulation/engine.py` | modify | Copy records from the same objective state as bodies. |
| `src/simulation/population_replay.py` | create | Pure checkpoint-plus-event fold for objective registration/lifecycle metadata, including incomplete admission witnesses. |
| `src/simulation/replay.py`, `src/simulation/persistence.py` | modify | Thread trusted in-process materialization context into scene replay/restore without changing durable codecs. |
| `src/api/observer_replay_context.py` | create | Read and validate stored runner config through the run-control port; return neutral replay context. |
| `src/api/app.py` | modify | Inject the context source when attaching `ObserverReadService`. |
| `src/simulation/observer_demographics.py` | create | Pure demographic/marker contracts and projection functions. |
| `src/api/observer_demographic_schemas.py` | create | Strict, separately versioned HTTP DTOs. |
| `src/api/observer_service.py` | modify | New read methods using existing cursor resolution. |
| `src/api/routes/observer.py` | modify | Two GET-only projection routes. |
| `tests/unit/test_observer_demographics.py` | create | Pure projection and lifecycle extraction tests. |
| `tests/unit/test_observer_demographic_api.py` | create | HTTP cursor, auth, pagination and immutability tests. |
| `tests/unit/test_observer_facts.py` | modify | Fact detachment and replay parity. |
| `tests/unit/test_observer_population_replay.py` | create | Real replay-service and event-prefix roster/stage reconstruction. |

## Task 1: Carry lifecycle facts through detached replay scenes

### Intent

Every demographic reading must describe the displayed objective cursor, not the latest live roster or runner configuration.

### Implementation Steps

1. Add `lifecycle_records: tuple[AgentLifecycleRecord, ...] | None = None` to `ObjectiveFacts` and `ObjectiveScene`; extend `SnapshotFacts` for the existing snapshot lifecycle field. `None` means channel absent or activation unknown; `()` means explicitly active with no admitted agents. Copy and validate in `_freeze_facts`. `WorldSnapshot.lifecycle_records` currently defaults to `()` and does not alone establish empty-channel activation: add optional `lifecycle_active: bool | None = None` to `scene_from_snapshot`. Explicit false with records is invalid; explicit true preserves active-empty; without the selector nonempty records prove activation and empty records remain unknown. Do not change durable snapshot schemas. API reads use engine-derived facts, which retain exact channel presence.
2. In `WorldEngine.detached_objective_facts`, copy activation from `self._population_lifecycle is not None` and records from `self._lifecycle_records` after objective replay, sort by agent identity, and detach the immutable records. Never derive engine channel presence from whether the collection is nonempty. Preserve the existing mutation guard.
3. Introduce frozen `ObserverReplayContext` in `simulation.replay` with exactly three optional static specs: `population_lifecycle`, `new_agent_initialization`, and `kinship_spec`. Add the latter two optional fields to Python-level `ReplayRequest`, thread all three through scene-helper keyword context and `ReplayService.replay` into existing restore arguments, and preserve existing unrelated replay inputs/defaults. No durable/wire schema changes. Inject an `ObserverReplayContextSource` protocol into `ObserverReadService`; its `read_context(run_id)` adapter in `observer_replay_context.py` calls `RunControlRepository.get(run_id)`, verifies payload SHA256/schema against the stored record, strictly decodes runner config, and copies exactly `config.population_lifecycle`, `config.new_agent_initialization`, and `config.kinship`. Never consult a live manager engine, owner state, or analysis. Wire it in `api.app._attach_persistence_services` through the existing repository constructor. Missing context remains valid for legacy/off snapshots; a lifecycle snapshot needing missing/invalid context returns safe503 `observer_replay_context_unavailable`/`observer_replay_context_invalid`, never guessed defaults or fabricated empty state. Runs without the required stored configuration remain explicitly unavailable; this plan does not add archive import or subjective recovery.
4. Add a pure `fold_population_metadata` in `simulation/population_replay.py` taking checkpoint registrations/lifecycle records, ordered committed events, and validated lifecycle/run identity inputs. Reserve `AgentCreated` metadata without admitting a body; carry `AgentInitializationRecorded` as a witness; add registration/lifecycle only at `AgentEnteredWorld`; apply `LifecycleStageChanged` to the matching record. Resolve initial stage/dependency using the existing lifecycle policy and assigned lifespan using the existing seed-derived lifespan function, not a new random stream. Reject duplicate/mismatched/missing witnesses and retain incomplete reservations as pending metadata, not admitted population. Death leaves the historical record intact; life status comes from folded bodies. No cognition invocation or demographic-policy execution occurs during this fold.
5. Invoke that single metadata helper from `WorldEngine.restore_from_snapshot` over events after the checkpoint and from `_apply_event_prefix` over the selected prefix. Rebuild registrations, lifecycle tuple and registration translator together before extracting facts. Fold only events after the checkpoint once; do not reapply initialization to an already present agent. Preserve the existing world projector for bodies/physics, tick/revision and journal semantics. Align lifecycle/initialization applicability with the accepted version taxonomy, including latest selected replay-v22/codec-v20; do not expand support by unvalidated numeric/string comparisons. This is a scoped repair of read-only historical materialization, not a new simulation policy or restart guarantee.
6. Exercise both scene helpers through `ReplayService`, with a checkpoint strictly before an admission/stage change, as well as direct engine folds. Before `AgentEnteredWorld`, reserved identities are not counted; after it, body/record/registration match even when the tick prefix is not complete. No private-world import in observer/API and no restored engine survives the returned history.
7. Leave `ObserverAgent`, `ObserverFrameOut`, `_frame_out`, stream envelopes, and `observer-protocol-v1` unchanged. These new internal facts feed separate endpoints only.

### Required Interfaces and Contracts

- Existing constructors remain valid via the default `None` field. Legacy and feature-off facts produce unavailable demographic metadata, not fabricated generation 0 or age 0.
- Records and bodies must come from one folded state. Validate duplicate agent/body bindings and reject records referencing absent bodies.
- The live engine's authoritative mutation path is unchanged. Read-only folds must reproduce stored objective admissions/stages, not rerun admission rules, mortality, cognition or population policies. Unsupported/corrupt historical context is explicitly unavailable rather than reconstructed from current live settings.
- No objective kinship graph is added to the ordinary frame; genealogy comes from lineage APIs in Phase 2/4.

### Requirement Evidence

User request: location-based, read-only observer. `.ai-factory/ARCHITECTURE.md` — Objective authority and runtime, Versioned Extension Contract. `docs/observer.md` — live/start-of-tick/event-prefix cursor semantics.

### Error Handling and Logging

Use `ObjectiveFactsError` safe codes for malformed detached bindings; no silent record drops. DEBUG: run, resolved tick, record/body counts, channel presence. Never log records, genealogy, content, or credentials.

### Tests

Add absent/active-empty/normal/dead-body records; duplicate/missing bindings; frozen copies; unchanged engine tick/revision/journal; live-restored equality at entry/stage/death boundaries. Use real replay repositories with a checkpoint before later entries, not just an already-correct snapshot. Test prefixes immediately after Created, InitializationRecorded, EnteredWorld and StageChanged; complete-prefix equality with next tick; two entrants in one tick; repeated fold rejection; absent/mismatched config context; and accepted older/latest codec families. Exercise `api.app` service attachment and never rely only on an injected prebuilt scene.

### Acceptance Criteria

Historical scenes contain only records committed at that cursor. Feature-off frame serialization is unchanged. No observer receives private authority.

### Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_observer_facts.py tests/unit/test_observer_population_replay.py tests/unit/test_observer_demographics.py tests/architecture/test_observer_isolation.py -q`

Expected: all pass with coverage enabled.

## Task 2: Publish demographic population and selected-roster projections

### Intent

Supply all overlay labels and population counts from the backend while keeping large rosters bounded on the wire.

### Implementation Steps

1. Introduce pure frozen contracts and `project_demographics(scene, *, requested_tick, through_sequence, section, agent_id, after_agent_id, after_group_key, limit)` in `src/simulation/observer_demographics.py`. Input is detached `ObjectiveScene`, not `WorldEngine`. `section` is the closed selector `agents|cohorts|generations` (default agents); return exact full-population scalar totals plus only one bounded row section.
2. For active lifecycle, reuse `build_population_progress` with the exact scene bodies/records and resolved scene tick. Copy exact living/admitted/dead/max-generation totals; do not call analysis metrics. Stage rows are sorted by `(stage, life_status)` and capped at200 with explicit `stage_counts_truncated`; they never alter scalar totals. Page cohort rows by `(generation_index, entry_tick, cohort_id)` and generation rows by generation index; never embed unbounded cohort/generation arrays in `population`. Count travelers once through their bodies, never once per endpoint location.
3. Agent rows are ordered by stable `agent_id`, with `entity_id`, `entry_tick`, `generation_index`, `cohort_id`, `stage`, `dependency_status`, `life_status`, and `age_ticks`. Compute `age_ticks` through `chronological_age` only for living bodies. For dead bodies return `age_ticks=null`, `age_reason_code="dead_age_not_projected"`; display last recorded stage explicitly, not an imagined postmortem age. No lifespan predictions or biological birth assertion.
4. Add `ObserverReadService.demographics` and GET `/v1/simulations/{run_id}/observer/demographics`. Accept `tick`, `through_sequence`, `section`, optional exact `agent_id`, `after_agent_id`, `after_group_key`, `limit` (default100, maximum200 and no greater than configured API page ceiling). `agent_id` is allowed only in agents section and is mutually exclusive with either continuation; return zero/one matching row without scanning earlier pages. A known run whose agent is absent at that cursor returns no row with `selection_state="not_present_at_cursor"`; it is not a feature-disabled response. Resolve through the same context-aware history methods as `state`.
5. New strict response `observer-demographics-v1`: `run_id`, requested tick/sequence, `resolved_tick`, `revision`, `evidence_class="objective"`, availability/reason, section, selection state, nullable population totals/stage rows, and three row arrays `agents`, `cohorts`, `generations` (only the selected section can contain rows), `next_after_agent_id`, `next_after_group_key`, limit. Inactive continuations are null. Population scalar totals always cover the entire resolved roster, not the page or selected agent. Group continuation is an opaque bounded base64url encoding of the last canonical group key plus section/tick/sequence; strict decode rejects shape/selector/cursor mismatches. It is an objective keyset position, not an authorization credential.
6. Require explicit tick for all continuations; repeat identical tick/sequence/section. Reject unknown/duplicate keys, sequence without tick, incompatible selectors, invalid limits, bad continuation shapes and continuation without tick. The client pins every first/page/selection request to the displayed cursor. Enforce a 1MiB UTF-8 response ceiling, returning safe `observer_demographics_response_too_large` rather than silently dropping records or sending an unbounded document. Set `Cache-Control: no-store`.

### Required Interfaces and Contracts

- `availability="available"` plus zero counts is legal only for an active, complete empty lifecycle channel. Feature-off returns `availability="unavailable"`, reason `lifecycle_disabled`, `population=null`, empty agents, no continuation.
- Generation and cohort are distinct stored labels. Never infer either from age, ordering, names, family links, or a location.
- This is an independent sibling schema; do not silently append demographic fields to existing protocol-v1 frame objects.
- GET requires objective inspection. Unknown run/cursor errors follow `state`; no read commits a tick or writes a snapshot.

### Requirement Evidence

User request — demographic visualization/overlays. `docs/generational-runner.md` — Generation, cohort, and community; Admission, death, and capacity order. Architecture — optional channels and exact schema identity.

### Error Handling and Logging

Malformed active bindings fail closed, not as zero. INFO route status/count/duration; DEBUG cursor/revision/counts; WARN safe availability codes. No bodies, records, content IDs used as payload substitutes, tokens, or URLs containing credentials in logs.

### Tests

Exercise feature-off legacy reference, active-empty, founders plus later cohorts, aging/stage change, death/arrival same tick, transit, 201-agent pagination, exact selection beyond the first800 agents, selection absent before admission, thousands of cohorts/generations, every section/continuation combination, response ceiling, unknown keys, absent auth, exact start-of-tick/partial-prefix/full-prefix reads, and read-only journal high-water. Assert scalar totals are identical on all sections/pages/selection reads at one cursor and dead age is null. Test stage truncation explicitly rather than reporting a capped stage list as complete.

### Acceptance Criteria

Overlays can render every field without client demographic arithmetic. Population totals are correct before/after turnover and historical seeking. Existing state responses remain byte-equivalent for representative legacy fixtures.

### Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_observer_demographic_api.py tests/unit/test_observer_api.py tests/unit/test_v1_regression_gate.py -q`

## Task 3: Publish admitted-generation timeline markers

### Intent

The timeline receives genuine admitted-generation markers from a backend projection, not a guessed schedule or roster diff.

### Implementation Steps

1. Add `project_generation_markers` to `src/simulation/observer_demographics.py`. Group committed lifecycle records by generation; emit one row per admitted generation using minimum entry tick. Generation 0 is labeled founders. Missing/capacity-denied generations produce no marker.
2. Each row has `generation_index`, `first_entry_tick`, `seek_tick`, admitted count at the pinned high-water, and `label_code` (`founders` or `generation_first_admission`). Founders seek tick 0; later markers seek `first_entry_tick + 1`, the boundary after the admission tick. Restrict output to rows whose seek boundary is within the pinned committed history. Do not present tick-start before admission as the arrival state.
3. Add GET `/v1/simulations/{run_id}/observer/generation-markers` and matching service method. Query: required `tick` (sealed objective high-water), optional `from_tick`, `to_tick`, `after_generation_index`, `limit` 1–200/default100. Window filters refer to `seek_tick`; require `0 <= from_tick <= to_tick <= tick` when supplied. Canonical order and continuation use generation index ascending, with first-entry tick carried as data.
4. Response `observer-generation-markers-v1`: run, resolved tick/revision, availability/reason, marker rows, `next_after_generation_index`, limit. Same feature-off behavior and inspection capability as demographics. No unbounded range scan through events is necessary; use resolved lifecycle records.

### Required Interfaces and Contracts

Marker labels mean first successful admission in a calendar generation, not genealogy depth or scheduled generation boundaries. Markers do not claim subjective restart. This endpoint accepts full boundaries only; no `through_sequence` selector. During event-prefix viewing use the last full boundary at or before the view, clearly separate from the selected event marker.

### Error Handling and Logging

Reject unsupported query keys, duplicate keys, reversed/future windows, negative generation/limit values and ahead-of-head cursors. Log only safe cursor/count/reason metadata. Feature-off and no admitted generations are distinguishable.

### Tests

Founders, two cohorts in one generation, skipped admission slot, death of all members of an earlier generation, range filters, pagination and future-window rejection. Assert marker seek reaches the first admitted body and backward seeking before that boundary does not show it.

### Acceptance Criteria and Verification

`uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_observer_demographics.py tests/unit/test_observer_demographic_api.py -q`

Expected: marker identity/order remains stable as later generations are admitted; no invented marker exists for a denied slot.

## Phase Risks and Mitigations

- Channel presence can be confused with an empty collection: carry explicit `None` versus tuple and test active-empty.
- Two HTTP reads can race a live tick: the client pins the first demographic request to the displayed frame cursor and rejects mismatched tick/revision.
- Existing historical documents contain old counts: no semantic event, command, runner, result, replay, codec, metric or migration version is changed here.

## Phase Completion Checklist

- All three tasks meet acceptance criteria and focused tests pass.
- Existing observer frame schemas and authority checks remain unchanged.
- Update progress only in `index.md` after verification.
