# Implementation Plan: Deterministic Simulation Branching

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-04
Improved: 2026-10-04 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete milestone; this plan adds research-only simulation forking over deterministic replay and does not claim `multi_hop_testimony_tracking` or any new capability flag.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=auto
INFO [aif-plan] interpreted `ultra` as full mode (rich named plan); neither `fast` nor `full` was literal, matching prior v2 plan convention
INFO [aif-plan] plan name prefix v2- applied per user request; git.create_branches=false so stem is description slug
INFO [aif-plan] resolved plan file: .ai-factory/plans/v2-simulation-branching.md (format=slug)

## Compatibility contract

This plan extends deterministic replay into research simulation branching while preserving the observer playback protocol. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants stay intact. `WorldEngine` remains the only objective mutation authority on each run. Forking never rewrites parent history, never inverse-replays events, and never injects research truth into cognition. Parent and child are distinct durable runs.
2. No new capability flag. No `V2CapabilityFlags` slot. Unowned `multi_hop_testimony_tracking` still fails closed with `capability_unimplemented`. Architecture interventions expand named presets into existing modes/flags only — no runner `architecture_id` schema key.
3. V1 regression gate stays green under flags-off and tracing-off. Catalog A–E and the reference scenario keep current `exact_trajectory_hash` values. Branching is not appended to `tests/unit/test_v1_regression_gate.py`.
4. Schema bumps use accepted-set + exact key-set discipline. Default event write stays unchanged. Branch lineage is control-plane metadata (Alembic `0015` + optional observer fields), not a rewrite of authoritative event payloads. Stay on `observer-protocol-v1`; additive optional branch fields only.
5. No scripted emergence. Interventions do not invent friend/enemy/leader/culture roles or milestone scripts beyond existing trusted experiment override patterns.
6. No LLM → world shortcuts. Fork APIs never convert LLM output into world mutations.
7. Experiments stay reproducible. The same `(parent_run_id, fork_tick, intervention fingerprint, seed-stream choice)` must mint the same child `run_id` and the same child trajectory when deterministic dependencies are replayed. Agent-generated counterfactual imagination (`CounterfactualScenario` / prospective rollouts) stays a separate cognition path.
8. Optional cognition tracing stays outside the objective fold. Tracing on versus off must not change parent or child `exact_trajectory_hash` when tracing is off on both. Forking does **not** clone cognition-trace rows.
9. Observed metrics / timeline compare artifacts stay analysis-only. They must not appear on `Observation` / beliefs / cognition stages.

## Goal

A researcher can select a checkpoint/tick on an existing run, apply **one** controlled research intervention, and continue a new child run while the parent stays immutable:

```text
parent run (unchanged)
  -> fork tick T
  -> ResearchIntervention (exactly one closed change)
  -> child run (new ObserverSource + lineage metadata)
```

Supported intervention examples (closed catalog):

- different memory architecture
- one modified belief
- one communication removed
- mortality disabled
- different cognitive budget
- different agent architecture (named preset expand)
- alternate deterministic seed stream **only when explicitly requested**

Lineage is first-class:

```text
parent_run_id -> fork_tick -> intervention_ref -> child_run_id
```

Every run/branch exposes the same Observer Protocol. Godot does not need different world rendering code for a fork — a branch is another replay/live `ObserverSource` with lineage metadata. Backend domain code must not render or fold two branches simultaneously.

## Design Decisions (locked)

### Research fork vs agent counterfactual

- **Research intervention** lives under `simulation` / `api` composition as `ResearchIntervention` + `BranchLineage`. It creates a new durable run. Experiment catalog/matrix arms may *call* the fork API later; `simulation` must not import `experiments`.
- **Agent counterfactual** stays in `agents.cognition.counterfactual` / `prospective` (`CounterfactualScenario`, `ImaginedFuture`). Those types must not be reused for research forks. Cross-imports that treat a research fork as an imagined alternative (or the reverse) are forbidden.
- Logging and docs use distinct terms: `research_fork` / `research_intervention` vs `counterfactual_scenario` / `prospective_rollout`.

### Fork materialization (self-contained child)

- Forking creates a **new** `run_id` with its own journal, snapshots, run control, and subjective stores.
- At fork tick `T` (same cursor meaning as observer/replay: state after events with `event.tick < T`, `world.tick == T`):
  1. Restore parent objective scene via existing `ReplayService` / `scene_at_tick` path (read-only on parent). Reject `fork_tick` above the parent durable head (`fork_tick_ahead_of_head`).
  2. Materialize a child bootstrap `WorldSnapshot` from that restored state (new snapshot ids scoped to child; recompute `integrity_hash` under child `run_id`).
  3. **Rematerialize** parent committed objective history for `event.tick < T` into the child journal: rewrite `run_id` / snapshot ids, recompute `commit_hash` / predecessor links / payload integrity with `simulation.journal` helpers. Do **not** bit-copy parent `CommitHash` values — `compute_commit_hash` includes `run_id`. The child remains a complete `ObserverSource` without dual-run folding in the domain layer.
  4. Clone subjective stores (episodic memory, beliefs, relationships, goals) for all agents as-of tick `T` into the child `run_id` scope via an explicit `SubjectiveClonePort`. Do **not** clone cognition-trace rows, scientific evidence manifests, or stream-outbox cursors.
  5. Rebase exported runtime checkpoints onto `child_run_id` (see Task 5b) before apply — `apply_runtime_checkpoint` rejects `run_id` mismatch.
  6. Apply exactly one `ResearchIntervention` to the child-only config and/or subjective clone.
  7. Open the child as a durable continuation from tick `T` (new `PersistentSimulationService` / runner + child `RunControlRecord`), never calling `open_durable` on the temporary parent restore engine.
- Parent rows, hashes, and head water marks are never updated by fork.
- **Idempotency:** identical fork configs derive the same `child_run_id`. If that child/lineage already exists with the same intervention fingerprint, return the existing result. A colliding id with a different fingerprint fails closed with `branch_identity_conflict`.

### Child run identity and seed streams

- Existing `derive_run_id(config)` stays seed-derived for ordinary runs.
- Child ids use a new helper `derive_branch_run_id(parent_run_id, fork_tick, intervention_fingerprint, seed_stream_token)` in `src/simulation/identifiers.py` (or adjacent branching module) so forks do not collide with seed-only ids and so identical fork configs reproduce the same child id.
- `intervention_fingerprint` is a canonical SHA-256 over the closed intervention record (kind + typed fields), not free text.
- Default seed-stream policy (**inherit**): on derivation-v3, copy the parent's `stochastic_identity` onto the child config so `objective_stream_identity` stays shared (`src/simulation/randomness.py`). Do not substitute the child `run_id` into the stream identity. Alternate stream only when intervention kind `ALTERNATE_SEED_STREAM` is selected; never silently reseed.
- Legacy derivation-v1/v2 parents (stream identity = `run_id`) are out of scope for inherit parity in this plan unless a dedicated fixture proves otherwise; prefer forking derivation-v3 runs.

### Closed intervention catalog

Add frozen contracts in `src/simulation/branching.py` (facade-exported). Exactly one intervention per fork request.

| Kind | Effect on child only |
| --- | --- |
| `MEMORY_ARCHITECTURE` | Set target agent(s) `MemoryMode` (`reference` / `reconstructive` / `reconstructive_v2`) via runner-config clone; schema bump rules follow existing memory mode allowlists |
| `BELIEF_PATCH` | Replace/revise one owner belief id with a closed patch (proposition identity + value); fails closed if belief missing at fork |
| `COMMUNICATION_REMOVE` | Target a parent `Talked` / `Asked` / `Told` by `event_id` or `(tick, sequence)`. Require `event.tick >= fork_tick` so the event is **not** in the child prefix (`event.tick < fork_tick`). Fail `intervention_past_event` when the event is already in the prefix. Lineage records the removed communication for compare. Mid-tick surgical omit while keeping later same-tick sibling events is **out of scope**. Never rewrite parent history. |
| `MORTALITY_DISABLED` | Set run/cognition mortality modes to disabled on child config |
| `COGNITIVE_BUDGET` | Set `CognitiveBudgetMode` / limits on target agent(s) on child config (existing v22 rules) |
| `AGENT_ARCHITECTURE` | Resolve a named `architecture_id` via `agents.cognition.architectures.get_architecture` and apply the resulting modes/flags into the child's agent cognition specs (no `architecture_id` persisted in runner JSON). **Forbidden:** `simulation` importing `experiments.architectures` / `experiments` |
| `ALTERNATE_SEED_STREAM` | Explicit new deterministic `StochasticIdentity` (or documented seed-stream token) for the child; required fields documented; forbidden unless this kind is selected |

Reject unknown kinds, multiple interventions in one request, and empty patches with stable reason codes. Do not reuse `experiments.interventions.StoryTruthSpec` / milestone arbiter types for these research forks (story interventions remain experiment-coordinator concerns).

### Lineage persistence

- Alembic head advances `0014` → `0015`.
- Add table `simulation_branches` (name exact) **outside** `AUTHORITATIVE_TABLES` (control-plane genealogy, not objective event fold):
  - `child_run_id` PK/FK → `simulation_runs.run_id`
  - `parent_run_id` FK → `simulation_runs.run_id`
  - `fork_tick` (int ≥ 0)
  - `intervention_kind` (text; closed set)
  - `intervention_fingerprint` (sha256 hex)
  - `intervention_canonical` (JSONB; exact key-set per kind)
  - `branch_id` (stable derived id string)
  - `created_as_of_parent_head` (parent head tick at fork time; metadata only)
- Root runs have no row. Listing children is an index query on `parent_run_id`.
- Update `ALEMBIC_HEAD_REVISION` pin + compatibility matrix notes the same way `0014` was pinned.
- Encode/decode helpers live in `simulation` (domain contracts) with persistence adapter in `persistence/`.
- Repository methods support idempotent create: `put_lineage` / `get_lineage` / `list_children` plus lookup-by-child for conflict detection.

### Observer / playback compatibility

- Stay on `observer-protocol-v1`. Do **not** rename the protocol.
- Extend `ObserverManifest`:
  - `run_id` — **always required** (root and fork)
  - `parent_run_id` (optional; fork-only)
  - `fork_tick` (optional; required when parent present)
  - `intervention_summary` (optional; short closed summary string or fingerprint reference — no utterance text, no belief payloads)
  - `branch_id` (optional; present on forks)
- Mirror the same fields on `ObserverManifestOut` (`extra=forbid`, declare fields). Root runs omit/null the fork-only optionals.
- Also surface lineage on `ObserverRunOut` / `GET .../observer/run` for client convenience (same fields). Frames/`ObserverWorldState` stay free of branch genealogy.
- `LiveObserverSource` / `ReplayObserverSource` accept lineage and pass `run_id` (+ optional fork fields) into `manifest()` only. Projection/frame code paths stay unchanged aside from threading lineage into the manifest builder.
- Godot: parse optional fork keys with `.get`; show lineage in status/inspector; switching branches = switch `run_id` and reconnect to the same observer routes. **No** dual-world viewport, **no** second fold pipeline in Python domain packages. Dual-timeline compare UI is out of scope for this plan.

### Branch query APIs (research control / inspection)

Add `/v1` routes (capability `simulation_control` for mutating fork create; `objective_inspection` for lineage reads):

| API | Behavior |
| --- | --- |
| `POST /v1/simulations/{parent_run_id}/branches` | Create fork from `fork_tick` + one intervention; returns child run + lineage (idempotent on identical fingerprint) |
| `GET /v1/simulations/{run_id}/branches` | List child branches (keyset pagination) |
| `GET /v1/simulations/{run_id}/branch` | Locate parent lineage for this run (`parent_run_id`, `fork_tick`, intervention summary) or `404`/`branch_root` for roots |
| `GET /v1/simulations/{run_id}/branch/fork-point` | Seek corresponding fork point: returns parent/child ids + fork tick + observer cursor pair for that tick |
| `GET /v1/simulations/{run_id}/branch/state` | Obtain branch current state: thin envelope pointing at existing observer/replay head (`ObserverRunOut`-compatible facts + lineage) — does not invent a second world projector |

Domain service: `BranchService` in `src/simulation/branch_service.py` (contracts in `branching.py`) with ports for run repo, snapshot/event rematerialization, subjective clone, runtime-checkpoint rebase, lineage store, and run-control write. `api` wires adapters. `simulation` must not import `api` / `persistence` / `observer` / `experiments`.

### Timeline comparison (not dual render)

- Add inspection helper `compare_branch_timelines` in `src/simulation/branch_compare.py` (not `analysis` — API cannot import analysis) that, given two run ids sharing lineage (or an explicit fork pair):
  - verifies shared prefix through `fork_tick` (payload-equivalent events; commit hashes may differ by `run_id`)
  - reports first diverging `(tick, sequence)` / reason code
  - reports trajectory hashes for post-fork windows (`exact_trajectory_hash` when run ids match by design; otherwise document replica-normalized use)
  - optional event-kind counts
- Must not load two live engines for rendering. Prefer detached journal reads + existing hash helpers in `runner_serialization.py`.
- This plan ships API/DTO + unit proofs, not a Godot dual viewport.

### Logging

- Domain: stdlib loggers (`simulation.branching`, `observer.sources`).
- API: `infrastructure.logging.get_logger`.
- DEBUG: parent/child run ids, fork tick, intervention kind, fingerprint, branch id, rematerialized event/snapshot counts, reason codes.
- INFO: fork created (or idempotent hit), lineage listed, compare completed.
- Never log belief payloads, utterance text, seeds at INFO, credentials, or full intervention JSON at INFO (fingerprint + kind only).

## Non-Goals

- Rendering two branches simultaneously in the backend domain layer or Godot dual viewport / side-by-side compare UI
- Mutating or reseeding the parent run
- Inverse events / rewriting authoritative parent history
- Mid-tick surgical omission of one event while keeping later same-tick siblings
- Merging agent `CounterfactualScenario` with research forks
- Claiming `multi_hop_testimony_tracking` or adding a new `V2CapabilityFlags` slot
- `/v2` HTTP namespace
- Automatic matrix-factor expansion for every intervention kind (catalog/matrix arms may come later)
- LLM-authored interventions
- Cloning cognition-trace rows, scientific evidence, or stream-outbox cursors into the child

## Commit Plan

- **Commit 1** (after tasks 1–3b): `feat(simulation): add research branch lineage contracts and Alembic 0015`
- **Commit 2** (after tasks 4–6b): `feat(simulation): materialize deterministic forks from replay checkpoints`
- **Commit 3** (after tasks 7–9): `feat(api): expose branch create/lineage/compare observer metadata`
- **Commit 4** (after tasks 10–12): `feat(observer): thread branch identity; document and prove reproducibility`

Each checkpoint is a git commit on `main` created when those tasks are done. Do not squash them into one commit at the end. `git.create_branches` is false, so implementation stays on the current branch.

## Tasks

### Phase 1: Contracts, lineage store, identity

- [x] Task 1: Define research branching contracts and closed intervention catalog.
  - Deliverable: Add `src/simulation/branching.py` with frozen `ResearchInterventionKind`, `ResearchIntervention`, `BranchLineage`, `BranchCreateRequest`, `BranchCreateResult`, `BranchTimelineCompareRequest` / `BranchTimelineCompareResult`, and validation helpers. Exactly one intervention per request. Reject unknown kinds / missing fields with stable reason codes (`invalid_intervention`, `intervention_past_event`, `belief_not_found`, `architecture_unknown`, `fork_tick_ahead_of_head`, `branch_identity_conflict`, etc.). Export from `simulation` facade/`__all__`. Document the hard split from `agents.cognition.counterfactual` in module docstring. Unit tests cover construction, fingerprint stability, and rejection paths.
  - Logging: `[simulation.branching] intervention_validated kind=%s fingerprint=%s` at DEBUG; ERROR on reject with reason_code only.
  - Files: `src/simulation/branching.py`, `src/simulation/__init__.py`, `tests/unit/test_simulation_branching_contracts.py`.

- [x] Task 2: Add `derive_branch_run_id` and branch id helpers.
  - Deliverable: Extend `src/simulation/identifiers.py` with `derive_branch_run_id(...)` and `derive_branch_id(...)` using existing digest helpers (no Python `hash()`, no wall clock). Prove distinctness from `derive_run_id(seed-only)` and stability across repeated calls. Document that alternate seed streams participate in the digest only when that intervention kind is selected; inherit path uses a stable inherit token (not a new random stream).
  - Logging: DEBUG `branch_id_derived parent_run_id=%s fork_tick=%s branch_id=%s` (no seeds at INFO).
  - Depends on task 1.
  - Files: `src/simulation/identifiers.py`, `tests/unit/test_identifiers.py` (or new focused test module).

- [x] Task 3: Persist lineage with Alembic `0015`.
  - Deliverable: Migration `alembic/versions/0015_simulation_branches.py` creating `simulation_branches` as specified in Design Decisions. ORM model + repository port methods (`put_lineage`, `get_lineage`, `list_children`, get-by-child). Pin `ALEMBIC_HEAD_REVISION = "0015"` and update compatibility/alembic pin tests. Keep the table out of `AUTHORITATIVE_TABLES`. Integration/migration tests assert head and FK behavior.
  - Logging: persistence adapter DEBUG on insert/list with ids/counts only.
  - Depends on task 1.
  - Files: `alembic/versions/0015_simulation_branches.py`, `src/persistence/orm.py`, `src/persistence/sqlalchemy.py` (or dedicated adapter), `src/simulation/compatibility.py`, `src/simulation/persistence.py` (port protocols), `tests/unit/test_alembic_head_pin.py`, `tests/unit/test_compatibility_matrix.py`, `tests/integration/test_migrations.py`.

- [x] Task 3b: Define fork idempotency and identity-conflict rules.
  - Deliverable: Document and implement (port-level) create semantics: if `child_run_id` already exists and lineage fingerprint matches the request, return the existing `BranchCreateResult` without rematerializing. If the id exists with a different fingerprint (or mismatched parent/fork_tick), fail closed with `branch_identity_conflict`. Unit tests cover hit / conflict / first-create paths against an in-memory lineage fake.
  - Logging: INFO `research_fork_idempotent_hit child_run_id=%s fingerprint=%s`; ERROR `branch_identity_conflict` with ids only.
  - Depends on tasks 2, 3.
  - Files: `src/simulation/branching.py` and/or `branch_service.py`, `tests/unit/test_simulation_branch_idempotency.py`.

<!-- Commit checkpoint: tasks 1–3b -->

### Phase 2: Fork materialization and interventions

- [x] Task 4: Rematerialize objective prefix + child bootstrap from replay.
  - Deliverable: `BranchService.fork` restores parent at `fork_tick` via existing replay/scene APIs (read-only), writes child `RunManifest` + bootstrap snapshot with recomputed `integrity_hash`, **rematerializes** objective commits/events with `event.tick < fork_tick` under child `run_id` (recompute `commit_hash` / predecessor links via `compute_commit_hash` / journal helpers), and leaves parent head unchanged. Prove with an in-memory fake repository that parent event ids/hashes are untouched and child prefix verifies under `verify_commit_chain`. Reject `fork_tick` above parent head. Do not call `open_durable` on the temporary parent restore engine. Do not bit-copy parent commit hashes.
  - Logging: INFO `research_fork_objective_materialized parent_run_id=%s child_run_id=%s fork_tick=%s event_count=%s`; DEBUG snapshot/commit counts and rehash confirmation.
  - Depends on tasks 2, 3, 3b.
  - Files: `src/simulation/branch_service.py`, `src/simulation/journal.py` (reuse helpers; avoid drive-by refactors), `src/simulation/replay.py` (hooks only if needed), `tests/unit/test_simulation_branch_fork.py`.

- [x] Task 5: Clone subjective state into the child scope via an explicit port.
  - Deliverable: Define `SubjectiveClonePort` and implement adapters that clone owner-scoped episodic memory, semantic beliefs, relationships, and goals as-of tick `T` into `child_run_id`. Fail closed if the clone is partial (`subjective_clone_incomplete`). Explicitly **exclude** cognition-trace rows, scientific evidence manifests, and stream-outbox cursors. Unit tests prove owner isolation and that parent subjective rows remain unchanged.
  - Logging: DEBUG per-store clone counts (`memory_rows`, `belief_rows`, …); ERROR on incomplete clone.
  - Depends on task 4.
  - Files: `src/simulation/branch_service.py`, `src/simulation/persistence.py` (port protocol), persistence subjective/memory adapters as needed, `tests/unit/test_simulation_branch_subjective_clone.py`.

- [x] Task 5b: Rebase runtime checkpoints onto the child `run_id`.
  - Deliverable: Add `rebase_runtime_checkpoint(checkpoint, child_run_id)` (or equivalent pure helper) that rewrites only run-scoped identity fields so `SimulationRunner.apply_runtime_checkpoint` accepts the checkpoint on the child runner. Prove parent checkpoint `run_id` unchanged after rebase-from-copy; prove child apply succeeds; prove direct apply of an unrebased parent checkpoint still raises `run_id mismatch`.
  - Logging: DEBUG `runtime_checkpoint_rebased parent_run_id=%s child_run_id=%s ticks_committed=%s`.
  - Depends on task 5.
  - Files: `src/simulation/run_control.py` and/or `branch_service.py`, `tests/unit/test_simulation_branch_runtime_rebase.py`.

- [x] Task 6: Apply one closed research intervention and open child continuation.
  - Deliverable: After clone + rebase, apply the single intervention to child config/subjective state per the catalog table. Inherit parent `stochastic_identity` unless kind is `ALTERNATE_SEED_STREAM`. Apply `AGENT_ARCHITECTURE` via `agents.cognition.architectures.get_architecture` + mode/flag application inside simulation/composition — **never** import `experiments`. Then open child durable continuation from tick `T` through existing runner/persistence seams. Cover each intervention kind with at least one unit test; `COMMUNICATION_REMOVE` proves `intervention_past_event` when the event is already in the prefix and success when `event.tick >= fork_tick`; `ALTERNATE_SEED_STREAM` proves non-default path only when requested; `AGENT_ARCHITECTURE` expands presets without writing `architecture_id` into runner JSON. Record `BranchLineage` using Task 3b idempotency (transactional with child create).
  - Logging: INFO `research_fork_created parent_run_id=%s child_run_id=%s fork_tick=%s kind=%s fingerprint=%s`; DEBUG intervention application reason codes.
  - Depends on tasks 3b, 5, 5b.
  - Files: `src/simulation/branch_service.py`, `src/simulation/runner_models.py` (clone helpers only if needed), `src/agents/cognition/architectures.py` (read-only registry use), `tests/unit/test_simulation_branch_interventions.py`.

- [x] Task 6b: Persist child `RunControlRecord` for resume/rehydrate.
  - Deliverable: After successful fork materialization, write a child `RunControlRecord` with the cloned-then-intervened runner `config_payload` so API rehydrate/`SimulationManager` can see the child. Do not copy parent stream-outbox cursors or cognition-trace rows. Prove list/get control paths observe the child and that config payload bytes are never logged.
  - Logging: DEBUG `research_fork_run_control_written child_run_id=%s lifecycle=%s`; never log config payload.
  - Depends on task 6.
  - Files: `src/simulation/branch_service.py`, `src/simulation/run_control.py` (reuse types), persistence run-control adapter wiring, `tests/unit/test_simulation_branch_run_control.py`.

<!-- Commit checkpoint: tasks 4–6b -->

### Phase 3: API, observer metadata, compare

- [x] Task 7: Wire branch HTTP APIs.
  - Deliverable: Implement the five routes in Design Decisions under `src/api/routes/` (new `branches.py` or extend simulations router), schemas in `src/api/schemas.py` / observer schemas as needed, and composition in `SimulationManager` / persistence services. Authz: create = `simulation_control`; list/get/fork-point/state = `objective_inspection`. Create path must surface Task 3b idempotent hits and Task 6b control-plane visibility. Tests cover happy path, idempotent retry, identity conflict, root-without-lineage, unknown parent, fork_tick ahead of head, and capability failures.
  - Logging: route INFO/DEBUG with run ids, fork tick, kind, counts; no payloads.
  - Depends on tasks 6, 6b.
  - Files: `src/api/routes/branches.py` (or equivalent), `src/api/app.py`, `src/api/simulation_manager.py`, `src/api/schemas.py`, `tests/unit/test_branch_api.py`.

- [x] Task 8: Add branch timeline compare (simulation inspection, single-fold reads).
  - Deliverable: Implement `compare_branch_timelines` in `src/simulation/branch_compare.py` using detached journal reads — shared prefix check through `fork_tick` (payload equivalence; commit hashes may differ by `run_id`), first divergence, trajectory hash windows. Expose `POST /v1/simulations/branches/compare` (or under a run-scoped path) with `objective_inspection`. Forbid holding two live engines for render. Do not place this helper under `analysis` (API cannot import analysis). Unit tests: identical forks → no divergence after equal continuation; intentional belief patch → divergence after fork.
  - Logging: INFO `branch_timeline_compare parent=%s child=%s diverge_tick=%s diverge_sequence=%s`.
  - Depends on task 6.
  - Files: `src/simulation/branch_compare.py`, API route/schema, `tests/unit/test_branch_timeline_compare.py`.

- [x] Task 9: Thread branch metadata into ObserverManifest and ObserverRunOut.
  - Deliverable: `run_id` is **always required** on `ObserverManifest` / `ObserverManifestOut` / sources. Fork-only optionals (`parent_run_id`, `fork_tick`, `intervention_summary`, `branch_id`) per Design Decisions. `ObserverRunOut` mirrors the same. Sources and `ObserverReadService` load lineage when present. Root runs omit/null fork-only fields consistently. Stay on `observer-protocol-v1`. Tests prove every manifest carries `run_id`, roots lack fork fields, forks expose lineage.
  - Logging: DEBUG `observer_manifest_branch run_id=%s branch_id=%s parent_run_id=%s fork_tick=%s`.
  - Depends on tasks 3, 7.
  - Files: `src/observer/contracts.py`, `src/observer/sources.py`, `src/api/observer_schemas.py`, `src/api/observer_service.py`, `tests/unit/test_observer_branch_metadata.py`.

<!-- Commit checkpoint: tasks 7–9 -->

### Phase 4: Godot compatibility, reproducibility, docs

- [x] Task 10: Godot observer lineage surfacing without dual render.
  - Deliverable: Parse `run_id` plus optional branch fields from manifest/run JSON in `clients/godot-observer/`. Show parent/child/fork tick/intervention summary in status or inspector. Switching branches uses existing `start_with_run_id` / query `run_id` path — no second world renderer, no simultaneous folds, no compare viewport. Protocol tests/scripts updated. Unknown keys remain ignored safely.
  - Logging: `[observer.session] branch_lineage run_id=%s parent_run_id=%s fork_tick=%s` at DEBUG.
  - Depends on task 9.
  - Files: `clients/godot-observer/scripts/net/session.gd`, status/inspector scripts as needed, Godot protocol tests under `clients/godot-observer/tests/`.

- [x] Task 11: Reproducibility proofs for identical fork configurations.
  - Deliverable: Hard proofs (not smoke-only): (a) same parent + fork_tick + intervention fingerprint + seed-stream choice ⇒ same `child_run_id` / `branch_id`; (b) two independently created identical forks with deterministic fakes produce equal child `exact_trajectory_hash` (prefer equal child ids so exact hash matches); (c) parent `exact_trajectory_hash` unchanged after fork; (d) instantiate real `ResearchIntervention`, `CounterfactualScenario`, `ImaginedFuture`, and an ordinary `SemanticBelief` (non-matching predicate) and assert mutual exclusion by type/predicate — not class-object markers; (e) architecture test that `simulation.branching` / `simulation.branch_service` / `simulation.branch_compare` do not import `experiments`. Assert log tokens `research_fork_created` / idempotent hit and fingerprint equality.
  - Logging: tests assert presence of key log tokens and reason codes; failure messages use stable codes.
  - Depends on tasks 6, 6b, 8.
  - Files: `tests/unit/test_simulation_branch_reproducibility.py`, `tests/architecture/test_simulation_branch_boundaries.py`.

- [x] Task 12: Documentation checkpoint via `/aif-docs` ownership.
  - Deliverable: Update contributor docs for branching APIs, lineage, rematerialization/rehash, stochastic-identity inherit vs alternate, observer `run_id` + optional fork fields, idempotency, and the research-fork vs agent-counterfactual boundary (`docs/research-api.md`, `docs/godot-observer.md`, and a short section in `docs/architecture.md` or `docs/simulation-runner.md`). Mention Alembic `0015` and that Godot treats a branch as another `run_id` (no dual viewport). No README bloat beyond a one-line pointer if the landing page already links docs.
  - Logging: n/a (docs only); implementation logs already specified.
  - Depends on tasks 9–11.
  - Files: `docs/research-api.md`, `docs/godot-observer.md`, `docs/architecture.md` and/or `docs/simulation-runner.md`, `docs/persistence.md` (0015 note).

<!-- Commit checkpoint: tasks 10–12 -->
