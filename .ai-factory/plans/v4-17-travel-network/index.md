<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-17 Travel Network

Mode: ultra
Branch: main
Created: 2026-11-09
Plan identifier: `v4-17-travel-network`

## Original Request

v4-17 travel network

Naming requirement:

Use `v4-17-travel-network`.

Extend the location graph with route-level physical properties.

Support:

- travel time
    
- capacity
    
- risk
    
- infrastructure quality
    
- seasonal availability
    
- blockages
    

These are objective WorldEngine mechanics.

Agents may have inaccurate beliefs about route quality.

Infrastructure may alter route properties.

Support path planning based on subjective knowledge rather than omniscient graph access.

## Settings

- Testing: yes; full strategy. Unit, architecture, determinism, integration,
  Compose/browser, Godot regression, Research UI, benchmark regression, and
  static gates, with coverage enabled for Python lanes.
- Logging: verbose, metadata-only. Bounded DEBUG flow/counts, INFO milestones,
  WARN unresolved adjacency/truncation/partial coverage, ERROR safe codes.
  `PALIMPSEST_LOG_LEVEL` controls operational verbosity. Never log person sets,
  route/`infra-`/`msoc-`/`org-` payload bodies beyond safe counts, observation
  bodies, prompts, credentials, tokens, DSNs, memories, embeddings, utterance
  bodies, or payload surrogates.
- Docs: yes; mandatory `$aif-docs` checkpoint in Task 24.
- Language: English UI and artifacts; technical terms preserved.
- Git: enabled; base `main`; no branch or worktree creation; skip-push
  preference retained. Commit checkpoints are suggestions, not authorization to
  commit during planning or implementation unless the user explicitly asks.
- Workflow: slug IDs; normal verification with explicit complete required-gate
  certification.
- Naming: canonical stem `v4-17-travel-network`; the ultra bundle directory is
  `.ai-factory/plans/v4-17-travel-network/`, phase files use
  `phase-NN-<slug>.md`, and `index.md` is the canonical entrypoint.
- Research source: `.ai-factory/RESEARCH.md` and `.ai-factory/research/` do not
  exist; no external research conclusions are invented.
- Execution: plan only in this invocation. No implementation, commit, roadmap
  edit, or branch creation occurs while planning.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations (in progress)"
Rationale: V4-17 deepens the owned objective-world seams
`infrastructure_networks` and `regions_migration` with route-level physical
properties and fallible owner-scoped route beliefs, making travel time,
capacity, risk, infrastructure quality, seasonal availability, and blockages
objective `WorldEngine` mechanics without adding a V4 flag. This plan does not
edit or close the roadmap; `$aif-roadmap` must register V4-17 in M8 and record
the deepening ownership and write pair.

## Requirements Reconciliation

Authority: the Original Request defines scope; `.ai-factory/ARCHITECTURE.md`
("Key Principles", "Capability ownership", "Versioned Extension Contract",
V4-01 through V4-16 seams) and `.ai-factory/RULES.md` constrain every edit;
`.ai-factory/DESCRIPTION.md` and `.ai-factory/ROADMAP.md` describe current
state; `src/world/regions.py`, `src/world/infrastructure.py`,
`src/world/_rules.py`, `src/world/_perception.py`, `src/world/observations.py`,
`src/simulation/versioning.py`, `src/simulation/persistence.py`, and
`src/agents/cognition/regional_migration.py` define the concrete contracts.
`tests/architecture/test_v4_architecture_invariants.py` and related boundary
suites govern compatibility.

| Decision / supported combination | Source path and section | Verification evidence |
| --- | --- | --- |
| V4-17 deepens `infrastructure_networks` + `regions_migration`; adds **no** V4 context/flag; keeps 14 contexts / 12 flags / six owned; reuses accepted `runner-config-v56`; adds no `runner-config-v57` | Original Request; `v4_architecture.py` 184-197/330-332; `compatibility.py` 155-164; `runner_models.py` 325-334 | Task 1/3/21/25 |
| Activates deepening write pair event **27** / codec **`v25`** after reserved 23-26 / `v21`-`v24`; reserved pairs stay unchanged; infrastructure-only runs keep `(23, "v21")`; regions-only keep `(21, "v19")` | `versioning.py` 39-75; `persistence.py` 257-403; Original Request | Task 1/8/21 |
| Authority is `OBJECTIVE_WORLD`; owners `world` + `simulation`; no abstract planner, grid, coordinates, owner, crew, nation, or score | `v4_architecture.py` non-goals; `world/infrastructure.py` forbidden fields | Task 2/5/21 |
| Route-level properties are derived from existing `RouteSpec`, adjacency, `Season`/weather/`ActiveHazard`, and operational infrastructure assets; no new root runner key or config schema | `regions.py` 64-99/181-224; `environment.py` 56-104/249-285/431; `_infrastructure.py` 176-262 | Task 2/5 |
| Closed statuses: `open` / `restricted` / `closed`; seasonal availability `open` / `restricted` / `closed`; blockage causes `none` / `weather` / `seasonal` / `hazard` | Original Request; locked `travel-network.v1` | Task 2/5 |
| Movement uses one effective condition: closed rejects, restricted costs more, capacity and risk are enforced; `Move`, `Transport`, and `Flee` stop bypassing it | `_rules.py` 1126-1183/1212-1721/3222-3392/3947-4186 | Task 10/13 |
| Agents observe only adjacent exit condition; `remote_topology` stays omitted; no omniscient graph | `observations.py` 135-163/284-325; `_perception.py` 576-622 | Task 11/12/16 |
| Route-quality beliefs are owner-scoped destination memories plus existing `regional_migration` biases; no new ledger, mode, command, or checkpoint schema; stale/inaccurate beliefs are legal | `regional_migration.py` 65-466; `memory.py` 1273-1300; `migration_displacement.py` 706-754 | Task 14/15/16 |
| Infrastructure snapshot v2 adds bounded route rows; v1 remains decodable; same settings/store; a seventh GET route is added under `SUBJECTIVE_DEBUG` | `infrastructure_models.py` 32-37/294; `infrastructure_codec.py` 37-167; `api/routes/infrastructure_networks.py` 41/213-355 | Task 18/19/20 |
| Four metric families append 188 -> **192**; prior 188 ids/order/versions/value keys stay unchanged | `analysis/specifications.py` 53/262-265/9061-9064 | Task 17/21 |
| Observer semantics stay **73**; `route_condition_changed` aliases `WEATHER_CHANGED` | `observer/version.py` 11-166 | Task 6/21 |
| Commands stay **43**; Alembic stays **0017**; `/v1` and `observer-protocol-v1` stay | `.ai-factory/ARCHITECTURE.md` baseline; `migration_plan.py` 48-57 | Task 21/25 |
| Off-gate experiment `travel_network@1` registered; not on the V1 gate | `experiments/catalog.py` infrastructure precedent | Task 23/25 |
| Roadmap owned by `$aif-roadmap` | ARCHITECTURE requirement 7 | Task 24/25 `git status` |

### Supported combinations and availability transitions

| Input / validation | Retained state | Output / transition / side effects | Verification |
| --- | --- | --- | --- |
| `infrastructure_networks` off, no regions | No travel channel | Default write pair; no route rows | Task 3/21 |
| Infrastructure off, regions active | No travel channel | Regions pair `(21, "v19")`; legacy exits | Task 3/8 |
| Infrastructure active, regions absent | No travel channel | Infrastructure pair `(23, "v21")`; INFO `travel_network_inactive` | Task 3/8 |
| Infrastructure active, regions present | Travel channel active | Pair `(27, "v25")`; route conditions derived | Task 3/8/22 |
| Channel active, no environment spec | `season=None` | No seasonal deltas; availability open; weather/infrastructure still apply | Task 5 |
| Channel active, spring/summer | Season available | Open unless weather/hazard/infrastructure says otherwise | Task 5/9 |
| Channel active, autumn | Season available | Restricted, +1 duration, -1 capacity, +0.1 risk | Task 5/9 |
| Channel active, winter, quality < 0.5 | Season available | Closed `seasonal`; movement rejects | Task 5/9/10 |
| Channel active, winter, quality >= 0.5 | Season available | Restricted `seasonal`; infrastructure relief | Task 5/9/10 |
| Clear/cloudy weather | No weather delta | Status unchanged | Task 5 |
| Rain | Weather available | Restricted, +1 duration, +0.15 risk | Task 5/10 |
| Storm, quality < 0.5 | Weather available | Closed `weather` | Task 5/10 |
| Storm, quality >= 0.5 | Weather available | Restricted with infrastructure relief | Task 5/10 |
| Active hazard at either endpoint | Hazard available | Restricted, +0.3 risk, -2 capacity | Task 5/9 |
| Operational road/bridge | Infrastructure available | Quality/capacity relief; one duration/fatigue delta only | Task 5/13 |
| Damaged/destroyed/below-floor infrastructure | Infrastructure available | No quality/capacity contribution | Task 13 |
| Move/Transport/Flee on open route | Channel active | Admitted with condition duration/fatigue | Task 10 |
| Transport with 2 participants, capacity 1 | Channel active | Rejected `ROUTE_CAPACITY_EXCEEDED` | Task 10 |
| Any command on closed route | Channel active | Rejected `ROUTE_CLOSED` / `ROUTE_BLOCKED` | Task 10 |
| No belief / stale belief / closed belief | Cognition enabled | No bias / decayed bias / strong penalty; admission still authoritative | Task 14/15 |
| Checkpoint/replay v25/V27 | Channel active | Round-trips route rows; v21/v19 still decode | Task 7/8 |
| Dual gate unset | No reader | 503 `infrastructure_networks_disabled` | Task 19 |
| Another unowned V4 flag | Unchanged | `capability_unimplemented` | Task 21 |
| Env-gated lane missing prerequisite | No green certification | `unexecuted` + prerequisite | Task 25 |

No blocking open questions: every material decision is fixed below.

## Architecture and Decisions

1. **Deepen, do not add.** V4-17 owns no new V4 context or flag. It extends the
   already-owned `infrastructure_networks` context and the V3
   `multi_polity_migration` / `regions_migration` seam. Counts remain 14
   contexts / 12 flags / six owned.
2. **Activate `(27, "v25")`.** Register it in a separate deepening tuple after
   the reserved 23-26 / `v21`-`v24` pairs. Do not steal the epidemics,
   ecological-feedback, or disasters reservations. Infrastructure-only runs keep
   `(23, "v21")`; regions-only keep `(21, "v19")`.
3. **One authoritative route condition.** `WorldState.travel_network` stores a
   bounded ordered tuple of `RouteCondition` rows. It is seeded from existing
   facts at bootstrap and recomputed deterministically at tick boundaries.
   Intra-tick movement reads the start-of-tick condition; infrastructure,
   weather, season, and hazard changes take effect at the next tick boundary.
   Transitions are effect-complete events; no derived value is stored twice in
   conflicting places. The private `world._travel_network` module is added to
   both import-boundary allowlists and stays out of `world.__all__`.
4. **Locked policy `travel-network.v1`.** Constants and status precedence are
   fixed in Phase 2. No RNG, wall clock, planner, owner, or score participates.
5. **Status precedence.** Storm without relief -> closed weather; winter
   without relief -> closed seasonal; active hazard -> restricted hazard; storm
   with relief -> restricted weather; winter with relief -> restricted seasonal;
   rain/autumn -> restricted; otherwise open.
6. **Infrastructure quality and capacity.** Operational `ROAD` on the edge and
   `BRIDGE` at either endpoint contribute integrity and capacity. V4-16 travel
   deltas are applied once; route risk adds fatigue, never a random roll.
7. **Movement unification.** `Move`, `Transport`, and `Flee` all read the same
   condition. Closed rejects; restricted costs more; transport checks 2-person
   capacity; flee no longer uses raw `duration_ticks == 1`.
8. **Local observation only.** `VisibleExit` gains optional route facts for
   adjacent exits. `remote_topology` remains omitted. No global route table is
   exposed to cognition.
9. **Fallible beliefs reuse existing seams.** Route-quality evidence is stored
   in owner-scoped destination memories; `regional_migration` biases use it for
   bounded path planning and only bias the first visible hop. No new ledger,
   per-agent mode, command, or checkpoint schema.
10. **Objective research surface.** Extend the existing infrastructure snapshot
    to v2 with route rows, add a seventh GET route, and extend the existing
    Research UI/Godot panels. `experiments.collectors` populates the detached
    route analysis input from those snapshot rows. No new settings, store,
    credential, or database migration.
11. **Four metrics.** Append `travel_route_structure@1`,
    `travel_route_condition@1`, `travel_route_blockage@1`, and
    `travel_route_belief_alignment@1`; catalog 188 -> 192. No composite score.
12. **Observer semantics 73.** Alias `route_condition_changed` to
    `WEATHER_CHANGED`; do not add a semantic type.
13. **Pins.** Commands 43; default runner/result v4/v2; latest feature runner
    v55; v56 accepted; replay-v23/codec v21 remains for infrastructure-only;
    travel network uses replay-v27/codec v25; Alembic 0017; `/v1`;
    `observer-protocol-v1`.
14. **Off-gate experiment.** `travel_network@1` is trusted, reproducible, and
    never on the V1 gate.
15. **Roadmap not edited here.** `$aif-roadmap` owns milestone registration.

### Locked route-condition summary

| Dimension | Locked behavior |
| --- | --- |
| Base route | `RouteSpec` duration/fatigue, else duration 1 / fatigue `move_fatigue` |
| Infrastructure | V4-16 effective duration/fatigue applied once; operational road/bridge contribute quality and capacity |
| Season | Spring/summer 0; autumn +1 duration, -1 capacity, +0.1 risk; winter +2 duration, -2 capacity, +0.2 risk |
| Weather | Clear/cloudy 0; rain +1 duration, +0.15 risk; storm +2 duration, +0.5 risk |
| Hazard | +0.3 risk, -2 capacity; status restricted |
| Risk | endpoint visibility + `weather + season + hazard + 0.02*duration - 0.3*quality`, clamped 0..1 |
| Fatigue | infrastructure-effective fatigue + `risk * 2.0`, clamped >= 0 |
| Capacity | `min(8, origin.body_capacity, destination.body_capacity)` + road 2 + bridge 1 + season/hazard deltas, clamped 1..24 |
| Quality | Mean integrity of operational road/bridge contributors, 0 if none |
| Cap | `MAX_ROUTE_CONDITIONS = 512`; overflow fails closed |

## Phase Index

1. [Phase 1: Contract and Activation](phase-01-contract-and-activation.md) — Tasks 1-3
2. [Phase 2: Objective Route Channel](phase-02-objective-route-channel.md) — Tasks 4-6
3. [Phase 3: Replay, Checkpoints, and Tick Transitions](phase-03-replay-and-checkpoints.md) — Tasks 7-9
4. [Phase 4: Movement and Observation](phase-04-movement-and-observation.md) — Tasks 10-13
5. [Phase 5: Subjective Route Knowledge](phase-05-subjective-route-knowledge.md) — Tasks 14-16
6. [Phase 6: Analysis and Read-Only Surfaces](phase-06-analysis-and-surfaces.md) — Tasks 17-20
7. [Phase 7: Invariants, End-to-End, and Experiment](phase-07-invariants-and-e2e.md) — Tasks 21-23
8. [Phase 8: Documentation and Verification](phase-08-docs-and-verification.md) — Tasks 24-25

## Cross-Phase Dependencies

- Tasks 4-6 depend on Tasks 1-3.
- Tasks 7-9 depend on Tasks 4-6 (Task 7 on 4 and 6).
- Tasks 10-13 depend on Tasks 7-9 (Task 11 also on Task 5).
- Tasks 14-16 depend on Tasks 10-13.
- Tasks 17-20 depend on Tasks 7-9 and 10-13 (Task 17 also on Tasks 5 and 18; Task 18 produces the snapshot route rows it consumes).
- Tasks 21-23 depend on Tasks 1-20 (Task 22 on 21; Task 23 on 21).
- Tasks 24-25 depend on Tasks 21-23.

## Tasks

### Phase 1: Contract and Activation
- [x] Task 1: Register travel-network deepening write pair and pins ([details](phase-01-contract-and-activation.md#task-1-register-travel-network-deepening-write-pair-and-pins))
- [x] Task 2: Lock `travel-network.v1` route-condition contract ([details](phase-01-contract-and-activation.md#task-2-lock-travel-networkv1-route-condition-contract))
- [x] Task 3: Activate the travel-network channel ([details](phase-01-contract-and-activation.md#task-3-activate-the-travel-network-channel))

### Phase 2: Objective Route Channel
- [x] Task 4: Add `WorldState` route-condition channel and bootstrap seeding ([details](phase-02-objective-route-channel.md#task-4-add-worldstate-route-condition-channel-and-bootstrap-seeding)) (depends on 2, 3)
- [x] Task 5: Derive deterministic route conditions from objective facts ([details](phase-02-objective-route-channel.md#task-5-derive-deterministic-route-conditions-from-objective-facts)) (depends on 2, 4)
- [x] Task 6: Add replay-v27 event contract and observer alias ([details](phase-02-objective-route-channel.md#task-6-add-replay-v27-event-contract-and-observer-alias)) (depends on 2)

### Phase 3: Replay, Checkpoints, and Tick Transitions
- [x] Task 7: Project route conditions through replay ([details](phase-03-replay-and-checkpoints.md#task-7-project-route-conditions-through-replay)) (depends on 4, 6)
- [x] Task 8: Add codec v25 checkpoints and journal support ([details](phase-03-replay-and-checkpoints.md#task-8-add-codec-v25-checkpoints-and-journal-support)) (depends on 4, 7)
- [x] Task 9: Emit route-condition transitions at tick boundaries ([details](phase-03-replay-and-checkpoints.md#task-9-emit-route-condition-transitions-at-tick-boundaries)) (depends on 5, 8)

### Phase 4: Movement and Observation
- [x] Task 10: Enforce route conditions in movement rules ([details](phase-04-movement-and-observation.md#task-10-enforce-route-conditions-in-movement-rules)) (depends on 9)
- [x] Task 11: Expose route facts on `VisibleExit` ([details](phase-04-movement-and-observation.md#task-11-expose-route-facts-on-visibleexit)) (depends on 5, 9)
- [x] Task 12: Serialize and parity-check route observations ([details](phase-04-movement-and-observation.md#task-12-serialize-and-parity-check-route-observations)) (depends on 11)
- [x] Task 13: Integrate infrastructure quality and fix movement inconsistencies ([details](phase-04-movement-and-observation.md#task-13-integrate-infrastructure-quality-and-fix-movement-inconsistencies)) (depends on 10, 11)

### Phase 5: Subjective Route Knowledge
- [x] Task 14: Persist route-quality beliefs in destination memories ([details](phase-05-subjective-route-knowledge.md#task-14-persist-route-quality-beliefs-in-destination-memories)) (depends on 11)
- [x] Task 15: Plan paths from bounded subjective route beliefs ([details](phase-05-subjective-route-knowledge.md#task-15-plan-paths-from-bounded-subjective-route-beliefs)) (depends on 14)
- [x] Task 16: Guard subjective route knowledge against objective leakage ([details](phase-05-subjective-route-knowledge.md#task-16-guard-subjective-route-knowledge-against-objective-leakage)) (depends on 15)

### Phase 6: Analysis and Read-Only Surfaces
- [x] Task 17: Append four travel-network metric families to 192 ([details](phase-06-analysis-and-surfaces.md#task-17-append-four-travel-network-metric-families-to-192)) (depends on 5, 9, 18)
- [x] Task 18: Extend infrastructure snapshot to v2 with route rows ([details](phase-06-analysis-and-surfaces.md#task-18-extend-infrastructure-snapshot-to-v2-with-route-rows)) (depends on 5, 9)
- [x] Task 19: Publish routes through existing read-only surfaces ([details](phase-06-analysis-and-surfaces.md#task-19-publish-routes-through-existing-read-only-surfaces)) (depends on 18)
- [x] Task 20: Add Research UI and Godot route presentation ([details](phase-06-analysis-and-surfaces.md#task-20-add-research-ui-and-godot-route-presentation)) (depends on 19)

### Phase 7: Invariants, End-to-End, and Experiment
- [x] Task 21: Enforce architecture invariants and pin sweeps ([details](phase-07-invariants-and-e2e.md#task-21-enforce-architecture-invariants-and-pin-sweeps)) (depends on 1-20)
- [x] Task 22: Add in-process travel-network end-to-end coverage ([details](phase-07-invariants-and-e2e.md#task-22-add-in-process-travel-network-end-to-end-coverage)) (depends on 21)
- [x] Task 23: Register off-gate `travel_network@1` experiment ([details](phase-07-invariants-and-e2e.md#task-23-register-off-gate-travel_network1-experiment)) (depends on 21)

### Phase 8: Documentation and Verification
- [x] Task 24: Documentation via `$aif-docs` ([details](phase-08-docs-and-verification.md#task-24-documentation-via-aif-docs)) (depends on 21-23)
- [x] Task 25: Required-gate verification certification ([details](phase-08-docs-and-verification.md#task-25-required-gate-verification-certification)) (depends on 22-24)

## Commit Plan

- **Commit 1** (after tasks 1-3): `feat(world): add travel-network contract and activation`
- **Commit 2** (after tasks 4-6): `feat(world): persist and replay route conditions`
- **Commit 3** (after tasks 7-13): `feat(world): enforce route conditions in movement and observation`
- **Commit 4** (after tasks 14-20): `feat(research): add subjective route planning and travel-network surfaces`
- **Commit 5** (after tasks 21-25): `test,docs: certify travel-network pins and required gates`

Commit checkpoints are suggestions only. Do not commit during `$aif-implement`
unless the user explicitly authorizes commits.

## Definition of Done

- V4-17 adds no V4 context or flag; 14 contexts / 12 flags / six owned remain.
- Route conditions exist for every adjacent edge when the channel is active,
  with locked `travel-network.v1` derivation and a 512-row cap.
- `Move`, `Transport`, and `Flee` enforce closed/restricted/capacity/risk through
  one condition; no bypass remains.
- Adjacent `VisibleExit` exposes route status, availability, blockage, capacity,
  risk, quality, duration, and fatigue; remote topology stays omitted.
- Owner-scoped destination memories carry route-quality beliefs, and bounded
  subjective path planning biases only the first visible hop.
- Write pair `(27, "v25")` is registered as a deepening pair; reserved 23-26 /
  `v21`-`v24` are unchanged; v21/v19 checkpoints still decode.
- Infrastructure snapshot v2 carries route rows; v1 remains readable; seven
  GET-only routes share the existing dual gate; the real collector populates the
  detached route analysis input.
- Four metric families append to exactly 192; observer semantics stay 73;
  commands stay 43; Alembic stays 0017.
- The in-process E2E uses real `WorldEngine` admission and route-transition
  events; boundary allowlists include the private `world._travel_network`
  module.
- Off-gate `travel_network@1` is registered; docs land with positive and
  negative parity checks; required gates are certified or explicitly
  `unexecuted` with prerequisites; roadmap untouched.

## Verification Receipt

Executed 2026-11-09 after final code and docs edits.

| Lane | Command | Result |
| --- | --- | --- |
| Python unit + architecture (coverage) | `uv run pytest tests/unit tests/architecture --cov=src --cov-report=term -q` | **9969 passed**, 0 failed, 79% coverage, 36:14 |
| Focused revalidation after final perception cast | `uv run pytest tests/unit/test_travel_network_perception.py tests/unit/test_regional_travel_perception.py tests/unit/test_world_perception.py -q` | **15 passed** |
| Ruff | `uv run ruff check src tests` | **All checks passed** |
| mypy | `uv run mypy src tests` | **Success**, 2317 files |
| Import-linter | `uv run lint-imports` | **25 kept, 0 broken** |
| Integration (non-scale) | `uv run pytest tests/integration -m "not scale" -q` | **46 passed**, 60 skipped, 5 deselected |
| Compose config | `docker compose config` | exit 0 |
| Research UI tests | `npx vitest run` (pinned pnpm unavailable) | **287 passed** (59 files) |
| Research UI check | `npx svelte-check --tsconfig ./tsconfig.app.json` | **0 errors, 0 warnings** |
| Godot regression | pinned Godot suite | **unexecuted** — prerequisite: Godot binary/export templates unavailable |
| Compose/browser lane | browser acceptance | **unexecuted** — prerequisite: unattested image/browser harness |
| Benchmark/scale regression | scale lane | **unexecuted** — prerequisite: scale hardware/database |
| PostgreSQL integration variants | opt-in DB-marked cases | **skipped** (60 skips in the non-scale lane) — prerequisite: PostgreSQL |

Roadmap: `.ai-factory/ROADMAP.md` has no V4-17 edit from this plan.
No commit, push, branch creation, or worktree operation was performed.
