# Implementation Plan: V2 Integration, Research Benchmark, and Observer Validation Suite

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-04
Improved: 2026-10-04 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete milestone; this plan closes the V2 research/integration surface by composing already-owned modes, metrics, observer, and zero-install startup into a validation suite without owning `multi_hop_testimony_tracking`.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M6 — Remaining V2 Capability Flags
INFO [aif-plan] mode=ultra treated as full (richer plan); remaining args describe the feature
INFO [aif-plan] resolved plan file: .ai-factory/plans/v2-integration-research-benchmark-observer-suite.md (format=slug)
INFO [aif-plan] plan name prefix v2- applied per user request; git.create_branches=false so stem is description slug
INFO [aif-improve] applied refinement: protocol-only Task 2; smoke helper Task 3 + Task 11b full suite; ToM reframe without wrong/corrected catalog arms; group churn not scripted shock; Task 16 zero-install only; Task 13 control checklist gap-fill; locked condition_ids + COMMUNICATION_REMOVE fork; Task 15b architecture + Task 17b Research UI; unit-test deny-list for emergence phrases; commit plan realigned

## Compatibility contract

This plan is a **composition and validation** plan. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants intact. `WorldEngine` remains the only objective mutation authority. Cognition still receives immutable per-agent `Observation` / `Perspective` only. Benchmark collectors, observer fixtures, and acceptance tests never feed analysis labels back into cognition, memory, prompts, or action selection.
2. Capability flags stay opt-in and default-off. Do **not** add a new `V2CapabilityFlags` slot. Do **not** own or implement `multi_hop_testimony_tracking` (still fails closed with `capability_unimplemented`). Do **not** invent new cognition modes or runner-config schema bumps unless an existing builder already requires a known write schema for an enabled mode.
3. V1 regression gate stays green under flags-off and tracing-off. Catalog A–E and the reference scenario keep current `exact_trajectory_hash` values. The V2 benchmark suite, observer graphical scenario, zero-install acceptance, and scientific-invariant gate stay **off** `tests/unit/test_v1_regression_gate.py`.
4. No scripted emergence. Forbidden: boolean `myth_must_emerge` / `group_must_form` / `culture_emerged` / `norm_emerged` / `society_formed` fields or assertions. Scenarios prove that **mechanisms required for emergence work** and that **metrics can detect the phenomenon when it occurs**. Absence, weak support, and strong support are all valid outcomes.
5. No LLM → world shortcuts. Prefer deterministic fakes; when LLM cognition is exercised, use `llm.recording` record/cache/replay only.
6. Experiments stay reproducible. Shared-seed paired/matrix arms keep shared scenario and stochastic identity. Canonical quantized metric output under `analysis.numerical` — not BLAS bit-identity.
7. Optional cognition tracing stays outside the objective fold. Observer presentation coordinates must not affect simulation outcomes.
8. Observed metrics stay separate from agent-visible state. Subjective and objective state remain strictly separated.

## Goal

Deliver the final V2 integration surface as several **small reproducible scenarios**, plus one deterministic **graphical observer** scenario, a **zero-install** startup acceptance gate, and a **scientific invariants** completion gate.

V2 is treated as research-complete for this suite when:

- V1 invariants still hold;
- graphical observers cannot change outcomes;
- presentation coordinates cannot affect simulation;
- subjective and objective state remain strictly separated;
- long-term goals and planning work;
- advanced reconstructive memory works;
- reflection works;
- Theory of Mind works;
- strategic communication works;
- skills and production work;
- emergent social/cultural processes can be measured without scripting outcomes;
- experiments run in batches;
- LLM cognition can be recorded/replayed;
- forked simulations can be compared;
- Godot observer provides usable live/replay visualization;
- Research UI provides deeper analysis;
- normal project startup requires neither Godot installation nor manual Godot build/export;
- long-running simulations remain operational within documented performance limits.

This plan does **not** claim that every emergent phenomenon always appears. It claims that the substrate, metrics, observer, and startup path are validated.

## Locked scope decisions

1. **Compose, do not reinvent.** Reuse catalog builders A–AD, existing scenario helpers (`environmental_scenario`, `territorial_scenario`, `group_formation_scenario`, …), matrix/`research_runner`, branching/`ResearchIntervention`, observer protocol, Godot fixtures, Research UI mounts, and published `./run.sh` path. Prefer thin wrappers + contracts over new WorldEngine semantics.
2. **Scenario contract is mandatory.** Every benchmark scenario declares: `scenario_id`, configuration, seed strategy, expected invariants, measurable outputs, non-goals, and statistical comparison approach (or explicit `n/a` with reason). Store as typed dataclasses + markdown catalog tables in docs.
3. **Small scenarios, not one mega-demo.** Target short tick budgets (prefer ≤ 64 ticks for unit/integration; default smoke helper ≤ 4 ticks). Observer graphical scenario may run longer but must remain CI-bounded. One phenomenon focus per scenario.
4. **Detection ≠ mandate.** Assertions check mechanism engagement (modes on, audits emitted, metrics available, support bands computable) and, where a controlled stimulus is applied, that metrics move in the expected **direction or detectability class**. Never assert “a myth must emerge” or “a group must form.”
5. **New catalog letters are optional.** Prefer a `v2-benchmark-suite` registry that references existing experiment condition ids. Add a new catalog experiment only if composition cannot reuse an existing arm without lying about its contract.
6. **Separate gates.** Keep `test_v1_regression_gate.py` untouched for new cases. Add `tests/unit/test_v2_scientific_invariants.py` (network-free) and extend `tests/compose/` for zero-install / observer acceptance (`pytest.mark.compose`, off default suite).
7. **Observer controls are product requirements.** Pause, event-step, tick-step, seek back/forward, large jump, return-to-live, filter, follow agent, causal debugger, fork switch must be covered by Godot protocol tests (gap-fill existing `session.*` APIs) and/or compose browser automation against the published image for smoke-level replay only.
8. **Zero-install acceptance fails closed.** Treat normal deployment as failed if a researcher must install Godot, open the editor, install export templates, manually export, or compile visualization assets. Acceptance environment: Docker/container runtime + browser only.
9. **Builder protocol before builders.** Task 2 wires callable slots / fail-closed stubs only. Tasks 4–11 fill concrete builders. Task 11b runs the full 16-scenario smoke. Do not claim Task 3 is a complete suite gate.
10. **Emergence-phrase deny-list is test-only.** Do not parse English phrases at registry runtime. Unit tests over registered invariant strings reject forbidden mandate language.
11. **Out of scope:** owning `multi_hop_testimony_tracking`; new capability flags; natural-language world dictionary; scripting social outcomes; changing `observer-protocol-v1`; dual-viewport fork rendering; production auth redesign; new Experiment L “wrong vs corrected ToM” catalog arms.

## Scenario catalog (locked)

Each row is a small scenario. Substrate = existing builders/metrics to wrap. Invariants are mechanism/availability invariants, not emergence mandates.

| # | scenario_id | Focus | Primary substrate | Locked condition / composition | Measurable outputs (examples) | Statistical comparison |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `bench-01-seasonal-planning` | Long-term planning under seasonal scarcity | Experiment U (`initial_goals` LONG_TERM already on arms) | `u-learned` vs `u-naive` | goal lifecycle counts; harvest/stockpile actions by season; `environmental_dynamics@1`; `goal_completion@1` | multi-seed matrix; planning-ahead action-rate distribution |
| 2 | `bench-02-memory-interference` | Memory interference changing behavior | Experiment A reconstructive-V2 | `a-reconstructive-v2` vs `a-reconstructive` (shared seed) | `memory_dynamics@1` interference/source-confusion; action-class Δ | paired arms same seed |
| 3 | `bench-03-reflection-revision` | Reflection revising a false belief | Experiment G | `g-deterministic` vs `g-disabled` | reflection audits; belief revision events; confidence-band change (analysis truth only) | on/off reflection; revision rate after contradictory evidence |
| 4 | `bench-04-tom-social-failure` | Incorrect ToM → measurable social failure **when** mismatch occurs | Experiment L (+ M ledger optional) | `l-enabled` (shared seed with #5); **not** a new wrong/corrected catalog arm | `theory_of_mind@1` mismatch indicators; failed cooperation/ask **rates when present** | multi-seed support/detectability — never “failure must occur” |
| 5 | `bench-05-tom-cooperation` | Successful cooperation using ToM **when** hypotheses help | Experiment L | `l-enabled`; same world/seed matrix as #4 | `cooperation@1`; handoff success **when present**; ToM support for partner goal | multi-seed success-rate CI; no mandated cooperation |
| 6 | `bench-06-deception-reputation` | Strategic deception and reputation consequences | Compose O strategy + Q reputation | Custom shared-seed arm on `runner-config-v10` with `CommunicationStrategyMode.DETERMINISTIC` **and** `ReputationMode.DETERMINISTIC` (plus `q-disabled` / strategy-only controls as needed). Do not pretend `o-enabled` alone carries reputation. | `communication_strategy@1` categories; `distributed_reputation@1` divergence | multi-seed; reputation shift after observed deception vs control |
| 7 | `bench-07-skill-specialization` | Skill learning and specialization | Experiments R + T | `r-enabled` and/or `t-enabled` vs disabled peers | `skill_learning@1`; `behavioral_specialization@1`; craft success rates | shared-seed specialization vs uniform |
| 8 | `bench-08-territorial` | Emergent territorial behavior | Experiment V | `v-scarce` vs `v-abundant` (+ disabled scarce if present) | claim ledger activity; `spatial_control@1` / `territorial_concentration@1` | existing V paired-world contract |
| 9 | `bench-09-social-clusters` | Formation and dissolution of social clusters | Experiment W | `w-enabled` vs `w-disabled` | group ledger churn; modularity/persistence **when present**; decay/retire churn **when present** | multi-seed `support_band` distribution — never boolean “group formed”; **non-goal:** scripted shock dissolution |
| 10 | `bench-10-norms` | Norm formation and violation | Experiment X | `x-enabled` vs `x-disabled` | norm ledger entries; violation observations; sanction/talk responses **when ledger non-empty** | on/off mode; response rate conditional on ledger |
| 11 | `bench-11-conventions` | Persistent convention/tradition | Experiment Y | `y-enabled` vs `y-disabled` | `persistent_social_conventions@1`; situation→action regularity | multi-seed persistence distribution |
| 12 | `bench-12-artifacts` | External artifacts preserving information | Experiment Z | `artifact_channel` vs `memory_only` | `external_artifact_memory@1`; later use after author absence/death **when terminal occurs** | present vs absent arms |
| 13 | `bench-13-naming-drift` | Vocabulary/naming drift | Experiment AA | `aa-enabled` vs `aa-disabled` | `emergent_semantic_naming@1`; invent/adopt/compete/forget counts | multi-seed drift vs convergence indicators |
| 14 | `bench-14-rumor-narrative` | Rumor → persistent inaccurate narrative | Experiment AB (+ E/P stimulus patterns only as needed) | `ab-enabled` vs `ab-disabled` | `cultural_narrative_lineage@1` / `rumor_distortion@1`; uplift gates | multi-seed support **when** inaccurate persistent variant occurs |
| 15 | `bench-15-architecture-matrix` | Identical world, different cognitive architectures | Experiment AC | `ac-<architecture_id>` arms | shared scenario fingerprint; valid closed commands; audit/metric availability diffs | shared-seed architecture factor |
| 16 | `bench-16-forked-intervention` | Forked replay after one controlled intervention | Branching | One `ResearchIntervention` with kind **`communication_remove`** (`ResearchInterventionKind.COMMUNICATION_REMOVE`); parent immutable; child post-fork hash diverges | lineage; prefix equality; `branch_compare` document | n/a: single deterministic intervention (not a culture matrix) |

### Per-scenario definition fields (locked schema)

```text
BenchmarkScenarioSpec:
  scenario_id: str
  title: str
  configuration: runner/experiment condition refs + required modes/flags
  seed_strategy: shared | paired | matrix factors + stochastic identity rules
  expected_invariants: list[str]   # mechanism + availability + authority invariants
  measurable_outputs: list[str]   # metric families, audits, counts
  non_goals: list[str]
  statistical_comparison: str | "n/a: <reason>"
  max_ticks: int
  off_v1_gate: true
```

Forbidden invariant language (enforced in **unit tests** over registry strings, not production parsers): “must emerge”, “must form”, “must invent myth”, “society forms”.

Allowed invariant language examples:
- “When `TerritorialClaimMode=DETERMINISTIC`, claim ledger updates are owner-scoped and analysis `spatial_control@1` is assemblable.”
- “Presentation seek/pause does not change `exact_trajectory_hash`.”
- “If narrative lineage rows exist, `cultural_narrative_lineage@1` reports support_band ≠ coding error / ABSENT for wrong reasons.”

## Observer graphical scenario (locked)

Add at least one deterministic scenario `observer-graphical-v2` containing:

- 5+ agents
- multiple Locations
- movement
- resources
- communication (Talk/Ask/Tell)
- item exchange
- weather/season change (`EnvironmentalDynamicsSpec`)
- crafting/building (production events + structures)
- one death or equivalent terminal event
- external artifact
- social information transmission

Validate Godot observer can (gap-fill against existing `session.gd` / protocol tests — do not rewrite working controls):

| # | Capability | Preferred proof |
| --- | --- | --- |
| 1 | start from initial state | existing fixture/session bootstrap + graphical fixture |
| 2 | consume live events | WS hello + event apply (compose smoke and/or protocol) |
| 3 | pause | `session.pause()` protocol test |
| 4 | step event-by-event | `seek_event` / `transport.step_target` gap-fill if missing |
| 5 | step tick-by-tick | `seek_tick` gap-fill if missing |
| 6 | seek backwards | seek to earlier tick/sequence |
| 7 | seek forwards | seek to later tick/sequence |
| 8 | jump thousands of ticks | fixture high-water ≥ 1000 **or** synthetic cursor; live gen may stay short |
| 9 | return to live | `session.return_to_live()` |
| 10 | filter event log | agent_id / event_type / location_id filters |
| 11 | select/follow agent | existing follow integration |
| 12 | open causal debugger | debugger panel protocol tests |
| 13 | switch to a forked run | `session.switch_run` + branch metadata |

Authority: observer remains read-only; client mutations rejected; layout coordinates presentation-only.

## Zero-install acceptance (locked)

Normal deployment fails if researcher must: install Godot, open editor, install export templates, manually export, or compile visualization assets.

Acceptance environment: Docker/container runtime + browser; **no** Godot installation.

Documented normal startup: `./run.sh` (aliases `./scripts/up.sh`, `docker compose up -d` on `compose.yaml`).

Verify:

1. required prebuilt images/artifacts are obtained;
2. backend becomes healthy;
3. Godot Web observer loads;
4. WASM initializes;
5. observer connects;
6. deterministic simulation can be viewed;
7. replay controls work (at least pause + seek or step against the running stack).

Extend existing `tests/unit/test_published_startup.py` (static) and `tests/compose/test_observer_browser.py` / `test_stack.py` (runtime). Do not make compose tests part of default `pytest`.

LLM recording/replay determinism is **not** part of the compose acceptance task — reuse `tests/integration/test_llm_recording_replay.py` (plus a thin suite contract pointer in the scientific-invariants gate).

## Design Decisions (locked)

### Package placement

| Piece | Location |
| --- | --- |
| Scenario registry + specs | `src/experiments/benchmark_suite.py` (facade exports from `experiments`) |
| Scenario builders (thin) | `src/experiments/benchmark_scenarios/*.py` importing catalog/scenario modules |
| Smoke helper | `src/experiments/benchmark_smoke.py` (or functions on `benchmark_suite`) — framework only until Task 11b |
| Matrix manifests for batch | `tests/fixtures/matrices/v2-benchmark-suite.json` (+ expand/summary unit tests); filesystem only; no HTTP batch |
| Observer graphical world | `src/experiments/observer_graphical_scenario.py` + Godot fixture under `clients/godot-observer/fixtures/` |
| Scientific invariants gate | `tests/unit/test_v2_scientific_invariants.py` |
| Architecture isolation | `tests/architecture/` (V1 gate exclusion + import boundaries) |
| Zero-install / browser acceptance | `tests/compose/` |
| Docs | `docs/v2-benchmark-suite.md` + cross-links in `docs/experiments.md`, `docs/godot-observer.md`, `docs/development.md` |

### Batch execution

Wire scenarios into `experiment-matrix-v1` / `palimpsest-matrix` where statistical comparison is required (scenarios 1, 2, 4–7, 8–11, 13–15). Scenario 16 uses branch compare APIs/tests rather than a culture matrix. Keep matrix off the V1 gate.

### LLM record/replay in the suite

Do **not** re-implement the recording stack. Scientific-invariants / suite contract tests assert the existing recording replay proof path remains importable and green (`tests/integration/test_llm_recording_replay.py`). Optional: one benchmark scenario documents `RecordingPolicy.REPLAY` as an allowed provider setting without making it the default (`deterministic_fake` remains default).

### Research UI

Do not rebuild Research UI. Task 17b adds acceptance that `/research/` serves when `PALIMPSEST_RESEARCH_WEB_ROOT` is set and that analytics/matrix views can resolve documents produced by benchmark matrix sidecars (reuse `tests/compose/test_research_ui_wiring.py` patterns).

### Performance bound

Reuse documented scale limits from `v2-long-experiment-scalability` (`@pytest.mark.scale` harness). Scientific invariants gate cites those docs; do not invent new BLAS-sensitive thresholds in this plan.

## Non-Goals

- Implementing `multi_hop_testimony_tracking`
- New `V2CapabilityFlags` fields or runner-config versions solely for naming the suite
- One giant demo world that scripts myths/groups/traditions
- Boolean emergence labels in metrics or tests
- Requiring Godot editor for researchers
- Putting the suite on `test_v1_regression_gate.py`
- Changing WorldEngine admission or Observation trust boundaries
- Dual simultaneous fold rendering in Godot
- New Experiment L wrong-hypothesis vs corrected-model catalog arms
- Scripted group-dissolution shock worlds
- Runtime English-phrase parsers in `benchmark_suite` production code
- Duplicating `llm.recording` integration tests inside compose

## Commit Plan

- **Commit 1** (after tasks 1–3): `feat(experiments): add V2 benchmark scenario registry and contract`
- **Commit 2** (after tasks 4–7): `feat(experiments): add cognition and social benchmark scenarios`
- **Commit 3** (after tasks 8–11b): `feat(experiments): add culture, architecture, fork scenarios and suite smoke`
- **Commit 4** (after tasks 12–14): `feat(observer): add graphical observer validation scenario and control suite`
- **Commit 5** (after tasks 15–16): `test(v2): enforce scientific invariants, architecture gates, and zero-install acceptance`
- **Commit 6** (after tasks 17–18): `docs(v2): document benchmark suite, Research UI acceptance, and V2 completion gates`

Each checkpoint is a git commit on `main` created when those tasks are done. Do not squash them into one commit at the end.

## Tasks

### Phase 1: Benchmark contract and registry

- [x] Task 1: Define `BenchmarkScenarioSpec` and registry API.
  - Deliverable: Add typed immutable specs (Pydantic-free dataclasses consistent with `experiments.models`) for scenario_id, title, configuration refs, seed strategy, expected invariants, measurable outputs, non-goals, statistical comparison, max_ticks, `off_v1_gate`. Registry lists all 16 `bench-*` ids as stable constants. **No runtime English-phrase parser** in production registry code. Unit tests cover registration completeness (exactly the 16 ids), facade export, and a **test-only deny-list** over registered invariant strings (forbidden mandate phrases).
  - Logging: DEBUG registry load; INFO `benchmark_suite_registered scenario_count=16`; ERROR only for structural validation (`benchmark_spec_invalid reason_code=%s`) without payloads.
  - Files: `src/experiments/benchmark_suite.py`, `src/experiments/__init__.py`, `tests/unit/test_benchmark_suite_registry.py`.

- [x] Task 2: Add builder **protocol** and fail-closed slots.
  - Deliverable: Define a builder protocol / callable type that returns `ExperimentDefinition` (and optional matrix factor grid) without duplicating catalog logic. Register all 16 scenario_ids with slots that fail closed (`builder_not_implemented`) until Tasks 4–11 fill them. Document the locked condition-id mapping table in the package docstring (must match the Scenario catalog above). Unit tests: unimplemented slot raises stable code; implemented stub (optional) builds one known arm.
  - Logging: INFO `benchmark_scenario_built scenario_id=%s condition_ids=%s max_ticks=%s` only when a real builder succeeds; DEBUG mode tokens only; ERROR `builder_not_implemented scenario_id=%s`.
  - Depends on task 1.
  - Files: `src/experiments/benchmark_scenarios/` (package + `__init__.py`), `tests/unit/test_benchmark_builders_protocol.py`.

- [x] Task 3: Network-free smoke **helper** (framework only).
  - Deliverable: Helper that, given a scenario_id with an implemented builder, builds with deterministic fakes, optionally runs ≤ 4 ticks (or the scenario’s smoke budget if lower), and returns availability of declared measurable outputs (metrics assemblable or audits present/ABSENT correctly). Does **not** assert emergence. Does **not** require all 16 builders yet — unit tests cover the helper against one temporary fixture builder or the first implemented arm once Task 4 lands. Full 16-scenario gate is Task 11b.
  - Logging: INFO `benchmark_smoke_finished scenario_id=%s ticks=%s metrics_available=%s`; ERROR fail-closed codes only.
  - Depends on task 2.
  - Files: `src/experiments/benchmark_smoke.py` (or `benchmark_suite` helpers), `tests/unit/test_benchmark_smoke_helper.py`.

### Phase 2: Cognition and social scenarios (1–7)

- [x] Task 4: Implement scenarios 1–3 (seasonal planning, memory interference, reflection revision).
  - Deliverable: Fill builders + specs + tests for `bench-01`…`bench-03` using locked condition ids (`u-learned`/`u-naive`, `a-reconstructive-v2`/`a-reconstructive`, `g-deterministic`/`g-disabled`). Assert mechanism engagement and metric/audit detectability; paired/matrix comparison hooks where listed. Planted false belief in #3 uses trusted experiment patterns (analysis truth only — never agent-visible `is_false`). Experiment U already carries LONG_TERM `initial_goals` — do not invent a second goal system.
  - Logging: scenario build/smoke logs; DEBUG belief/revision counts as integers only.
  - Depends on tasks 2–3 (helper available; not full-suite smoke).
  - Files: `src/experiments/benchmark_scenarios/` modules, reuse `environmental_scenario` / catalog A+G, unit tests.

- [x] Task 5: Implement scenarios 4–5 (ToM failure detectability and ToM cooperation detectability).
  - Deliverable: Shared-world/seed strategy using `l-enabled` (optional M ledger). **Do not** add wrong-vs-corrected catalog arms. Tests prove `theory_of_mind@1` / `cooperation@1` are assemblable and that mismatch/success indicators are **detectable when present**; multi-seed distributions allowed. Forbidden: asserting social failure or cooperation must occur on every seed.
  - Logging: INFO arm ids; DEBUG hypothesis mismatch / cooperation counts only.
  - Depends on tasks 2–3.
  - Files: benchmark modules wrapping Experiment L/M, tests.

- [x] Task 6: Implement scenario 6 (deception + reputation).
  - Deliverable: Compose strategy+reputation on `runner-config-v10` per locked catalog; assert `communication_strategy@1` and `distributed_reputation@1` measurable; controls vs enabled. Do not invent a second recording stack here.
  - Logging: category counts only — never utterance text.
  - Depends on tasks 2–3.
  - Files: benchmark modules, tests.

- [x] Task 7: Implement scenario 7 (skill learning + specialization).
  - Deliverable: Wrap R/T with locked ids; assert skill audits and specialization metrics; shared-seed contrast arms.
  - Logging: skill ids / success counts only.
  - Depends on tasks 2–3.
  - Files: benchmark modules, tests.
  <!-- Commit checkpoint: tasks 1–3 → Commit 1; tasks 4–7 → Commit 2 -->

### Phase 3: Culture, architecture, fork, suite smoke (8–16)

- [x] Task 8: Implement scenarios 8–11 (territory, clusters, norms, conventions).
  - Deliverable: Wrap V/W/X/Y with locked condition ids and phenomenon panels / family metrics. Tests assert ledgers update under DETERMINISTIC modes and support_band machinery runs; **forbid** boolean emerged assertions. For clusters: measure membership churn / decay / retire **when present**. **Non-goal:** inventing a scripted world shock to force dissolution.
  - Logging: ledger head counts; panel support_band codes.
  - Depends on tasks 2–3.
  - Files: benchmark modules, tests.

- [x] Task 9: Implement scenarios 12–14 (artifacts, naming drift, rumor/narrative).
  - Deliverable: Wrap Z/AA/AB with locked ids; artifact persistence after author absence/death **when terminal occurs** for #12; naming drift metrics for #13; narrative lineage + rumor distortion detectability for #14. Non-goals explicitly forbid scripting a myth.
  - Logging: artifact/label/narrative counts and opaque ids only.
  - Depends on tasks 2–3.
  - Files: benchmark modules, tests.

- [x] Task 10: Implement scenario 15 (architecture matrix).
  - Deliverable: Wrap Experiment AC (`ac-<architecture_id>`); prove identical world/seed across architectures; each architecture produces valid closed commands; suite records architecture digests as diagnostics only.
  - Logging: `architecture_id` + digest prefix; schema versions.
  - Depends on tasks 2–3.
  - Files: benchmark modules, tests reusing architecture contract patterns.

- [ ] Task 11: Implement scenario 16 (forked intervention).
  - Deliverable: Parent run → one `ResearchIntervention(kind=COMMUNICATION_REMOVE)` → child branch; assert parent history immutable; prefix equality; post-fork compare document; observer can address child `run_id`. Network-free unit/integration tests preferred.
  - Logging: fork_tick, parent/child run ids, compare hash equality flags — no payloads.
  - Depends on tasks 2–3.
  - Files: benchmark modules, `tests/unit/test_benchmark_fork_scenario.py`, reuse `branch_service` / `branch_compare`.

- [ ] Task 11b: Full 16-scenario smoke gate.
  - Deliverable: Network-free test that every registered `bench-*` builder is implemented and passes the smoke helper (≤ 4 ticks unless a scenario declares a lower budget). Assert metric/audit availability reporting only — no emergence booleans. Assert `tests/unit/test_v1_regression_gate.py` does not import benchmark suite modules or scenario ids.
  - Logging: INFO `benchmark_suite_smoke_ok scenario_count=16`; ERROR per-scenario reason codes.
  - Depends on tasks 4–11.
  - Files: `tests/unit/test_benchmark_suite_smoke.py`.
  <!-- Commit checkpoint: tasks 8–11b → Commit 3 -->

### Phase 4: Observer graphical scenario and controls

- [ ] Task 12: Build `observer-graphical-v2` deterministic world.
  - Deliverable: Trusted experiment/scenario builder with ≥5 agents, multi-location topology, resources, movement, communication, item exchange, environmental dynamics, crafting/building, one death/terminal, external artifact, social transmission. Emit runner config + fixture JSON for Godot offline play. Keep off V1 gate. Short executable arm for CI; optional longer recorded high-water (≥ 1000) for seek-jump tests.
  - Logging: INFO agent/location/event-type counts; ERROR if required semantic types missing from trace.
  - Depends on task 2.
  - Files: `src/experiments/observer_graphical_scenario.py`, `clients/godot-observer/fixtures/smoke/observer_graphical_v2.json` (or equivalent), Python tests for required event classes present.

- [ ] Task 13: Godot protocol/UI control checklist gap-fill.
  - Deliverable: Add or extend GDScript tests so the locked 13-row control matrix is fully covered. Prefer existing `session.pause` / `seek_event` / `seek_tick` / `jump_to_*` / `return_to_live` / `switch_run` / follow / debugger APIs. Document in test comments which row each test owns. Presentation-only: no simulation mutation. Register in `tests/run_protocol.gd`.
  - Logging: Godot harness INFO lines with reason codes; no tokens.
  - Depends on task 12.
  - Files: `clients/godot-observer/tests/*.gd` (extend `test_advanced_replay_integration.gd` or add focused files), fixtures, `tests/unit/test_godot_observer_fixtures.py` if needed.

- [ ] Task 14: Prove observer cannot change outcomes / presentation coordinates isolated.
  - Deliverable: Extend existing authority coverage (`tests/unit/test_observer_authority.py` patterns): identical seed runs with and without observer stream clients yield identical `exact_trajectory_hash`; layout catalog coordinate changes do not alter world events; client text frames still `client_mutation_rejected`.
  - Logging: hash compare INFO; ERROR on divergence.
  - Depends on tasks 12–13.
  - Files: `tests/unit/test_observer_authority.py` and/or focused new tests; architecture isolation only if new edges appear.
  <!-- Commit checkpoint: tasks 12–14 → Commit 4 -->

### Phase 5: Scientific invariants, architecture, zero-install

- [ ] Task 15: Add `tests/unit/test_v2_scientific_invariants.py` completion gate.
  - Deliverable: Network-free gate checking the scientific invariants list from Goal via imports/builders/docs pins: flags-off V1 profile still valid; subjective/objective separation; suite smoke registry complete; recording replay proof path exists (`tests/integration/test_llm_recording_replay.py` referenced/imported as contract); branch compare path exists; matrix CLI entry exists; Research UI static mount helpers exist; scale docs pin referenced. Do **not** append cases to `test_v1_regression_gate.py`. Explicitly assert suite does not enable unowned `multi_hop_testimony_tracking`.
  - Logging: INFO `v2_scientific_invariants_ok`; ERROR reason codes.
  - Depends on tasks 11b, 14.
  - Files: `tests/unit/test_v2_scientific_invariants.py`.

- [ ] Task 15b: Architecture isolation for the benchmark suite.
  - Deliverable: Architecture tests proving (a) V1 regression gate source does not reference `benchmark_suite` / `bench-` ids / `observer-graphical-v2`, (b) `experiments` still forbids `api`, (c) `src/` still does not import `clients/godot-observer`. Follow patterns in `tests/architecture/test_godot_client_isolation.py` / `test_causal_debugger_boundaries.py`.
  - Logging: assertion failures only (pytest).
  - Depends on tasks 11b, 12.
  - Files: `tests/architecture/test_benchmark_suite_isolation.py` (or extend existing isolation modules).

- [ ] Task 16: Zero-install + published observer acceptance.
  - Deliverable: Extend compose/browser acceptance so published path `./run.sh` / `compose.yaml` (no Godot on host) verifies: image pull/obtain, `/health` ok, `/` observer page, WASM init, observer connect/hello, deterministic sim view (reference or `observer-graphical-v2`), and at least one replay control (pause or seek) via Playwright. Static tests in `test_published_startup.py` gain any missing “no godot in launcher” assertions. Document `PALIMPSEST_API_IMAGE` requirement for CI. Keep `@pytest.mark.compose`. **Out of this task:** re-implementing LLM recording tests (covered by Task 15 contract pointer + existing integration file).
  - Logging: reuse `startup_*` / `observer_browser_*` reason codes; no secrets.
  - Depends on tasks 12–15b.
  - Files: `tests/compose/test_observer_browser.py` (extend), `tests/compose/test_stack.py` if needed, `tests/unit/test_published_startup.py`.
  <!-- Commit checkpoint: tasks 15–16 → Commit 5 -->

### Phase 6: Matrix, Research UI, docs

- [ ] Task 17: Wire matrix batch examples for statistical scenarios.
  - Deliverable: Example `experiment-matrix-v1` manifest(s) covering scenarios that declare statistical comparison; expand dry-run unit test; optional metric sidecars → `matrix-metric-summary-v1` smoke. Filesystem only; no HTTP batch start. Manifest condition ids must match the locked catalog.
  - Logging: matrix expand cell counts; aggregate write INFO.
  - Depends on task 11b.
  - Files: `tests/fixtures/matrices/v2-benchmark-suite.json`, `tests/unit/test_benchmark_matrix_manifest.py`.

- [ ] Task 17b: Research UI acceptance for benchmark artifacts.
  - Deliverable: Extend or add compose/unit checks that `/research/` serves when `PALIMPSEST_RESEARCH_WEB_ROOT` is set (reuse `test_research_ui_wiring.py`), and that matrix/analytics paths can resolve allowlisted sidecar/summary documents produced by the benchmark matrix fixture. No SPA feature rewrite. Skip cleanly when dist/env unset.
  - Logging: existing research UI smoke patterns; no tokens.
  - Depends on task 17.
  - Files: `tests/compose/test_research_ui_wiring.py` (extend) and/or focused unit tests for FS allowlist paths.

- [ ] Task 18: Documentation checkpoint (`Docs: yes`).
  - Deliverable: Add `docs/v2-benchmark-suite.md` with the 16-scenario table (including locked condition ids), observer graphical checklist, zero-install acceptance, scientific invariants, Research UI acceptance, and explicit non-assertions (no “must emerge”). Update `docs/experiments.md`, `docs/godot-observer.md`, `docs/development.md` cross-links; README one-line pointer if landing table already indexes experiments/observer. State M6 still open for `multi_hop_testimony_tracking`. Update `.ai-factory/DESCRIPTION.md` one-line surface note if accurate.
  - Logging: n/a for docs.
  - Depends on tasks 15–17b.
  - Files: `docs/v2-benchmark-suite.md`, `docs/experiments.md`, `docs/godot-observer.md`, `docs/development.md`, `README.md`, `.ai-factory/DESCRIPTION.md` as needed.
  <!-- Commit checkpoint: tasks 17–18 → Commit 6 -->

## Verification (implementer)

```bash
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_v1_regression_gate.py \
  tests/unit/test_v2_scientific_invariants.py \
  tests/unit/test_benchmark_suite_registry.py \
  tests/unit/test_benchmark_suite_smoke.py \
  tests/unit/test_benchmark_fork_scenario.py \
  tests/architecture/test_benchmark_suite_isolation.py \
  -q
uv run --frozen --python 3.12.14 pytest tests/integration/test_llm_recording_replay.py -q
# Godot protocol (CI/contributor with pinned editor or export stage):
# godot --headless --path clients/godot-observer --script res://tests/run_protocol.gd
# Compose acceptance (opt-in; needs Docker + PALIMPSEST_API_IMAGE + playwright):
# uv run --frozen --python 3.12.14 pytest -m compose tests/compose/test_observer_browser.py tests/compose/test_stack.py tests/compose/test_research_ui_wiring.py
./run.sh   # host must not need Godot
```

## Success criteria

- 16 benchmark scenarios registered with full contract fields, locked condition ids, and Task 11b smoke coverage
- Observer graphical scenario covers the locked entity/event checklist
- Observer control checklist covered by automated protocol tests (gap-fill, not rewrite)
- Zero-install acceptance proves Docker+browser path without Godot install/export
- Scientific invariants + architecture isolation gates green; V1 regression gate unchanged and green
- Research UI acceptance covers `/research/` + matrix artifact resolution when configured
- Docs describe mechanisms + detectability, not mandated emergence
- `multi_hop_testimony_tracking` remains unowned
