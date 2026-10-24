# Phase 5: Prebuilt browser acceptance and documentation

Plan: [index.md](index.md)  
Tasks: 11–12  
Depends on: Tasks 1–10

## Objective

Prove the generational observer works in the published Web export with no end-user Godot installation, while preserving the pinned engine and V2 regressions.

## Current-Code Evidence

| Path | Symbols / section | Why it matters |
|---|---|---|
| `clients/godot-observer/export/pins.env` | `GODOT_VERSION=4.7.2-stable`, SHA512 values | Exact existing editor/export pin; do not upgrade. |
| `scripts/export-observer-web.sh` | verified import and `Web` export | Existing reproducible artifact build. |
| `clients/godot-observer/export_presets.cfg` | Web, threads disabled | Browser compatibility. |
| `tests/compose/test_observer_browser.py` | `published_stack`, `test_published_observer_page_reaches_camp` | Image-based Playwright browser flow, asset checks and no-editor runtime assertions. |
| `tests/compose/start_reference.py` | `start_reference` | Test-side create/start/tick composition; observer client itself stays GET-only. |
| `src/experiments/generational_runner_scenario.py` | `generational_runner_scenario`, `_lifecycle` | Real Experiment BL: entry every2 ticks, generation length4, finite lifespan and cap8. |
| `src/api/durable_runner.py`, `src/api/simulation_manager.py` | `make_durable_runner_factory`, `SimulationManager` | Real persisted run-control payload, journal and snapshots must exist for observer replay; mounting lineage files alone does not create an observable world. |
| `src/simulation/runner.py` | `engine`, `set_intervention_arbiter` | Test producer can use an explicit trusted ordinary-command arbiter without adding API/client write controls. |
| `tests/unit/test_dependency_care_actions_replay.py` | existing committed care proofs | Reuse genuine feed/transport events, not fabricated UI activity. |
| `tests/unit/test_mentorship_teaching_uptake.py` | advice-input unit test | Distinguishes attempt/uptake modeling but uses constructed advice; it is not evidence that browser fixture learning emerged in a real run. |
| `.github/workflows/observer-image.yml` | protocol job | Currently lacks documented editor registration pass before script test. |
| `run.sh`, `run-dev.sh`, `Dockerfile` | launch/export composition | Published-image user flow versus contributor container build. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `tests/compose/start_generational.py` | create | Test-only real BL run composition and evidence validation. |
| `tests/compose/seed_generational_evidence.py` | create | Standalone test producer using installed public packages, real durable run setup and controlled native captured evidence; runnable in a one-off image container. |
| `tests/compose/test_observer_generational_browser.py` | create | Real exported browser acceptance, restricted/capture-off cases. |
| `tests/compose/conftest.py` | create/modify | Shared published stack plus parameterized generational stack with scoped credential settings, capture volume and one-off producer. |
| `tests/compose/test_observer_browser.py` | modify | Reuse shared fixture; preserve V2 smoke. |
| `tests/unit/test_godot_observer_fixtures.py` | modify | Validate new fixtures against backend schema. |
| `tests/unit/test_godot_protocol_mirror.py` | modify | Sidecar schemas do not widen legacy frame mirror. |
| `tests/architecture/test_godot_generational_boundaries.py` | create | GET-only/projection-only guards and unchanged pins. |
| `.github/workflows/observer-image.yml` | modify | Run editor registration before script suite and include new browser suite in existing image acceptance. |
| `clients/godot-observer/fixtures/smoke/generational_v3.json` | create | Acceptance manifest: expected controls, evidence classes and scenario identities. |
| `docs/godot-observer.md`, `docs/observer.md`, `docs/lineage-explorer.md`, `docs/development.md` | modify | User workflow, new read schemas, availability and verification. |
| `README.md` | modify | Update existing observer documentation index/feature summary only. |

## Task 11: Prove exported browser behavior and architecture noninterference

### Intent

Protocol-unit success is insufficient: verify actual browser rendering and API requests from the pinned prebuilt export, including missing/restricted evidence.

### Implementation Steps

1. Extract existing stack lifecycle into `tests/compose/conftest.py`, preserving unique Compose project names, sanitized failure logs and scoped teardown. Add a `published_generational_stack` fixture generating a temporary Compose override outside the repository: a project-named lineage volume is mounted read-only at `/srv/palimpsest/lineage` in API; a test-only `lineage-seed` service uses the same image, mounts that volume read/write and the single `tests/compose/seed_generational_evidence.py` file read-only at `/acceptance/seed.py`, and runs `python /acceptance/seed.py`. It imports installed application packages only, not the host tests package, Godot, or copied virtualenvs. If volume initialization requires root, scope that to the one-off writer and ensure published files are readable by the unchanged non-root API user. No production Compose/default/image change is needed.
2. Parameterize stacks for capture-disabled, capture-enabled inspect-only, and capture-enabled debug. Set `PALIMPSEST_LINEAGE_ROOT` only in enabled cases and existing `PALIMPSEST_API_AUTH_REQUIRED`, inspection/control/debug credential and debug-enabled settings through environment references in the temporary override. Use three different generated valid credentials; never bake them into YAML text, export, URLs or screenshots. `start_generational(base_url, control_token, inspection_token)` builds real BL seed23/horizon16 condition `bl-generational-unassisted`, submits encoded config/fingerprint with control headers, ticks through16, and reads expectations with inspection headers. Require backend proof of at least two nonfounder generations, stage changes and a committed death before browser assertions. This run remains the unmodified representative scientific artifact.
3. Implement `seed_generational_evidence.py` as a standalone asynchronous producer for a second, explicitly controlled evidence run. Use installed `SimulationManager`, `make_durable_runner_factory`, repository constructors and settings so the producer writes the same run-control config payload, run manifest, snapshots and journal as production composition. A producer-local runner-factory wrapper calls the normal durable factory, retains its public runner for capture, and attaches a trusted `set_intervention_arbiter`; no mutation/debug-seeding HTTP endpoint is introduced. Derive a separate finite v55 config from BL: add an explicit bootstrap `KinshipSpec` edge between two configured founders, enable its owned flag and `example_dependency_care_spec`, and provide a named FOOD item in the future adult caregiver's inventory. For this controlled run only, colocate founders and restrict entry spawn locations to that same existing location, set its body capacity to the configured population cap, and use `non_lethal_physical_rules` to avoid incidental starvation before the care demonstration; retain finite lifecycle/admission thresholds. The arbiter returns Wait until a founder is independent and a later infant is dependent, then submits one supported Feed using that inventory item. Determine participants from public `runner.engine.lifecycle_records`, `ordered_registrations`, and `detached_bodies`, not ID spelling; ordinary engine admission must accept the action. Require a committed feed event and finalized boundary with the target present; fail rather than inventing care if no eligible pair appears within the finite horizon. Transport actor/recipient rendering is proven separately by genuine committed-event protocol fixtures from the existing care action tests; it is not an optional browser prerequisite.
4. From that same retained run at finalized boundary B, publish objective genealogy using `extract_kinship_source_edges`, `extract_agent_lifecycle_facts` and `project_genealogy_lineage`. Publish controlled native mentorship/knowledge snapshots through the existing native source DTOs/projectors and real `create_lineage_publisher`; all participant IDs must refer to this run's roster. Include one explicit attempt-only record, one evidence-positive record, a mentor bond and a knowledge-entry lineage with distinct agent/body IDs. These private native records are a **constructed presentation fixture**, not proof of spontaneous teaching or a successful live learner pipeline; label their source/coverage accordingly and do not promote them into objective events or inject them into cognition. Use at least one sparse/missing boundary and a partial-coverage snapshot in separate scopes/boundaries. Publication B/run ID must match the persisted world used by the browser. Producer stdout contains only a safe JSON expectation manifest: run ID, committed boundary, evidence counts, native root keys and expected participant identities; never credentials or record content. Await publication, close/drain producer resources, and verify objective state plus lineage endpoints through the actual running API before opening the browser. API reads must not create or repair any fixture file.
5. Browser checks: nontrivial WASM/assets/MIME; `/version` engine/protocol/revision; open the top-level Credentials panel before protected bootstrap succeeds, enter inspection and optional debug secrets into masked inputs, Apply, then assert input text is cleared. Open Population without selecting an agent; displayed totals equal backend values. Enable generation/cohort/stage overlays; generation-marker click performs a full-boundary state seek revealing the expected entrant; backward seek removes later entrants/restores counts. In the controlled evidence run assert actual death/care/token/link states where those facts are present, and navigate parent→child→Back, teacher→student, and a transmitted-content card using server-returned refs.
6. Drive real exported Godot controls through Playwright mouse/keyboard input, not a substitute HTML page or JavaScript state injection. Assign stable static acceptance IDs to the new controls. After layout, bounded DEBUG diagnostics may expose each control's presentation-only `get_global_rect` with its static ID, and after application expose safe tick/count/availability state. At a fixed browser viewport, tests use those rendered rectangles to click/input, then require both the expected network request/header and a changed applied UI/model state; no unconditional PASS marker is evidence. Never include input text, tokens or private payloads in diagnostic lines. Capture screenshots only after credential fields are cleared. Browser request listeners assert observer navigation emits GET/stream traffic only; exclude producer/control setup performed before browser navigation, never exclude arbitrary app writes.
7. Run separate cases: no lineage root unavailable, inspect-only private controls restricted, distinct inspection+debug secrets successfully render both objective world and private cards, exact missing boundary remains unavailable, partial coverage warns, complete-prefix frame permits lineage, partial-prefix frame refuses it, debug replacement/revocation clears private data, and stale run/seek replies never paint old links. Assert base objective playback continues after private403/503. Root lookup must exercise the real array family response and participants beyond one physical catalogue page in the native/API gates.
8. Add targeted architecture/route/fixture checks for no client demographic/pedigree inference, Python/client isolation, private-world boundaries, no API analysis imports, GET-only observer/lineage routes and unchanged engine/protocol/count pins. Assert reading optional projections leaves final objective fingerprint, config writes and journal high-water unchanged; distinguish these read-only tests from the explicitly controlled test producer's authorized ordinary commands.
9. In the CI protocol job add the pinned editor-registration pass before `run_protocol.gd`; run both Compose browser suites after building the same image. Preserve pin file/hashes, renderer, disabled threads and export checks. Run the producer as a test-only service, never a production startup dependency.

### Required Interfaces and Contracts

No user installs Godot: `./run.sh` still pulls a published runtime image and opens/serves its Web export. Contributor/CI builds may download the existing checksum-pinned editor/templates inside their current build process. The runtime image contains no Godot editor. Do not inspect or check generated build/cache trees into the implementation.

Test Compose overrides use a project-isolated disposable database name containing `palimpsest_test`; wire that same name into the database and API/producer DSNs and wait for migrations before seeding. Never reuse a developer database. The API capture volume is always read-only; only the test producer mounts it writable. Lineage artifacts/run IDs are test-owned, never user captures. Run IDs and publication boundaries are validated through the real API before browser assertions. Credentials are capability-specific and never enter URLs, console logs, exports or screenshots. The observer remains read-only even though the external producer/control helper legitimately creates the acceptance runs.

### Requirement Evidence

User request — pinned V2 version, prebuilt export, no installation, zero-install browser, read-only. `docs/development.md` — pinned two-pass protocol suite. `docs/lineage-explorer.md` — reader-only API/capture optional. Root `AGENTS.md` — exclusions and coverage.

### Error Handling and Logging

Missing Docker/Playwright/image/editor is a reported unexecuted gate, not successful acceptance. Fixture/projection mismatch fails with safe expected/actual counts and reason code. Retain redaction on Compose/browser failure output; never dump private record payloads or cursor/credential values.

### Tests and Verification

Focused Python:

```sh
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_observer_demographics.py tests/unit/test_observer_population_replay.py tests/unit/test_observer_demographic_api.py tests/unit/test_lineage_participants.py tests/unit/test_lineage_participant_api.py tests/unit/test_lineage_filesystem.py tests/unit/test_lineage_api.py tests/unit/test_lineage_pagination.py tests/unit/test_godot_observer_fixtures.py tests/unit/test_godot_protocol_mirror.py tests/unit/test_observer_export_pins.py tests/unit/test_experiment_bl.py tests/unit/test_experiment_bm.py tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py tests/architecture/test_godot_client_isolation.py tests/architecture/test_godot_generational_boundaries.py tests/architecture/test_observer_isolation.py tests/architecture/test_lineage_explorer_boundaries.py -q
```

Pinned Godot:

```sh
"${GODOT_BIN}" --headless --editor --path clients/godot-observer --quit
"${GODOT_BIN}" --headless --path clients/godot-observer --script res://tests/run_protocol.gd
```

Published-image acceptance:

```sh
docker build --build-arg PALIMPSEST_REVISION="$(git rev-parse HEAD)" -t palimpsest-api:ci .
PALIMPSEST_API_IMAGE=palimpsest-api:ci uv run --no-sync pytest --cov --cov-report=term -m compose tests/compose/test_observer_browser.py tests/compose/test_observer_generational_browser.py -q
```

Run `uv run ruff check src tests`, `uv run ruff format --check src tests`, `uv run mypy`, and `uv run lint-imports`. `pyproject.toml` already configures strict mypy over src/tests and Python3.12. Keep coverage enabled; do not use `--no-cov` to hide regressions. Compose pytest coverage measures the test process, not the separately running API container; report that distinction and use the network-free API/unit gates for backend coverage.

### Acceptance Criteria

All focused gates and the real exported browser suite pass; image engine is 4.7.2-stable, protocol remains v1, and no host editor/runtime editor is needed. Record skipped/unavailable gates explicitly rather than declaring complete verification.

## Task 12: Document evidence semantics and release the browser workflow

### Intent

Researchers can discover controls, distinguish demographic facts from private learning claims, and understand why missing lineage is not an empty society.

### Implementation Steps

1. Mandatory documentation checkpoint: invoke `$aif-docs` during implementation with the scoped changes below. Do not rewrite unrelated docs or generate a new documentation hierarchy.
2. `docs/godot-observer.md`: document published-image/browser launch, memory-only independent inspection/debug credential entry and Forget, global population controls without selection, overlays, group pagination, marker seek, selected-agent tabs and Back/Load more. Preserve no-host-Godot requirement and pin. Explain dead/unknown age, absent-at-cursor logical selection, stale live data and secret-free screenshots.
3. `docs/observer.md`: document independent demographic schema with section/filter/group continuations/byte ceiling and context-unavailable errors; distinguish full-boundary frames carrying event resume cursors from genuine prefixes. Document admitted-marker boundary. Replace the absent-family-care-chrome limitation only after implementation; do not imply new WorldEngine behavioral policy or subjective restart.
4. `docs/lineage-explorer.md`: document participant role filters,200-candidate scan versus physical-read budget, sparse pages, signed cursor purpose/publication binding, evidence-priority ordering, owner isolation, explicit capture boundary and existing capture setup. Source correction is catalogue read completeness, not changed stored artifact format. Do not infer teachers from speech/source-only knowledge edges; content keys remain opaque.
5. `docs/development.md`: document real BL plus separately controlled evidence producer, shared database/run identity, read-only API volume/writer-only seeder mount, distinct test credentials, pinned two-pass suite and both real browser tests. Explicitly label constructed mentorship presentation fixtures as such, not emergent-learning proof. Preserve image-build separation from user launch and report skipped prerequisites.
6. `README.md`: update existing observer summary/index link only. Plan remains linked to M7 but does not close it: `institutional_economy` and kinship cultural handoff remain deferred. Any roadmap status edit must be routed through its owner command; this plan does not silently add/close milestones.
7. Final implementation handoff records verification results, image revision, unchanged engine/protocol pins, supported availability states and any unexecuted gates. Do not archive this plan or push/commit automatically without the relevant user workflow.

### Required Interfaces and Contracts

Documentation describes implementation and tests, not promised spontaneous society outcomes. Generation is admission calendar, cohort is admission stratum, kinship is captured genealogy, care is committed action, mentorship is scoped belief/evidence, and learning evidence is not world truth. Important knowledge ordering is disclosed, bounded and not a new metric.

### Error Handling and Logging

Examples use placeholders/header credentials and never publish actual secrets, private content or cursor tokens. Missing mandatory docs checkpoint blocks task completion; unavailable browser prerequisite is recorded in verification rather than erased from docs.

### Tests and Verification

Review every new UI label and documented route against fixtures/OpenAPI; run relevant docs/link checks already configured in the project. Re-run pinned Godot suite and focused API suites after any documentation-driven contract correction. Manually verify `./run.sh` still uses published assets and does not invoke Godot or a build on the user's machine.

### Acceptance Criteria

All new controls and error states are documented, every request requirement is covered by an acceptance scenario, no accidental engine upgrade or migration exists, and all task evidence is recorded before marking the index complete.

## Phase Risks and Mitigations

- Headless tests can skip without prerequisites: completion reports explicitly identify absent gates and require real image browser proof for release readiness.
- Scientific BL may not naturally exhibit kinship/care/teaching: separate controlled captured-evidence acceptance from real demographic run; label both honestly.
- CI may depend on generated class cache: use documented registration pass, never inspect or commit `.godot`.

## Phase Completion Checklist

- Mandatory docs checkpoint complete and scoped docs agree with code.
- Real exported browser and V2 regressions verified, or explicit release blockers recorded.
- Final implementation changes remain within read-only presentation/projection scope.
- Update progress only in `index.md`.
