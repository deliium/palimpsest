# Phase 10: Acceptance, regression and documentation

Plan: [index.md](index.md)  
Tasks: 23–24  
Depends on: Tasks 1–22

## Objective
Prove the nineteen research surfaces, both navigation modes and seven link dimensions end to end; document true evidence/availability limits and report unexecuted optional gates honestly.

## Current-Code Evidence
| Path | Symbols | Why it matters |
|---|---|---|
| `tests/compose/test_observer_generational_browser.py` | exported browser/research fixtures | Existing real BL proof is distinct from constructed presentation evidence |
| `tests/unit/test_benchmark_research_ui_artifacts.py` | API/artifact resolution | Representative matrix data integration |
| `tests/unit/test_cultural_metrics_end_to_end.py` | cultural pair/comparison generation | Reuse real encoded artifacts rather than hand-shaped API-only JSON |
| `tests/architecture/test_lineage_explorer_boundaries.py` | package and read-only checks | New read layer must respect existing boundaries |
| `clients/research-ui/vitest.config.ts` | happy-dom suite | Add mounted behavior, not source-text assertions |
| `docs/development.md` | pinned Godot/testing procedure | Keep coverage and distinguish unexecuted prerequisites |

## Files to Change
Introduce `tests/compose/test_generational_research_ui_browser.py`, `clients/research-ui/src/research/acceptance.test.ts`; extend architecture/unit fixture tests and compose producer fixtures narrowly. Modify `clients/research-ui/vitest.config.ts` for mounted component tests, `docs/research-ui.md`, `docs/research-api.md`, `docs/godot-observer.md`, `docs/development.md`, `README.md` documentation index. No roadmap edits during planning; implementation completion linkage is governed by its owner workflow.

## Task 23: Add behavioral end-to-end and compatibility gates
### Intent
Ensure the feature is usable with real artifacts and permissions, not just many reachable placeholders.
### Implementation Steps
1. Add mounted Svelte smoke tests covering every requested surface with real protocol fixtures and deferred network handlers: all panel headings, meaningful numerical/graph/table output, selection changes, paging, coverage and evidence labels. Exercise missing/denied/partial variants without passing every test on placeholder text. Configure Vitest with the existing Svelte Vite plugin and browser resolution conditions; use Svelte `mount`, `unmount`, `flushSync`/`tick` and happy-dom, avoiding a new testing library. Pull this minimal harness setup forward into Task2 before its first mounted tests; Task23 expands coverage, not the initial prerequisite. Add deterministic Cytoscape geometry stubs for DOM tests and keep actual canvas/interaction proof in browser acceptance.
2. Extend the existing Docker/Playwright harness for the prebuilt `/research/` app and exported Godot. A real Experiment BL run (seed23/horizon16) proves actual demographic/generation output via API. Use the existing layout-compatible reference-location generational run for browser scenes; do not assert BL fits Godot's reference layout.
3. Publish controlled lineage/civilization fixtures at the same test run/boundary for network and map UI tests, clearly labelled presentation fixtures. Generate cultural pair/comparison from `tests/fixtures/matrices/v3-cultural-metrics.json` and `tests/fixtures/cultural_metrics/known-lineage-v1.json` using existing trusted test helpers. Compare frontend counts/identities with server responses; never claim constructed teaching/institutions demonstrate emergence.
4. Browser workflow: run→population→generation marker→cohort comparison→genealogy→teacher/student→knowledge/technology diffusion→culture/language/narrative→migration/society→institutions/offices/lineage→economy/projects; direct links/reload/back/forward; UI→Godot tick-only/agent/location/research entity→UI. Include T=0 with markers pinned at later H, Next through two generations after backward seek, duplicate cohort IDs resolved by full tuple, subjective civilization institution concept, office-succession lineage and analytical episode identity with no scope owner. Verify mounted Godot inspector text/actions and exact source/publication—not only URL/parser state. Actual cultural encoded `rows_json` and comparisons must produce numeric rows, intervals/status and binding notices rather than empty placeholders.
5. Security/regression: inspection-only cannot load debug sources, debug credentials never appear in URL/history/logs; denied-source network requests stay separate; stale response after run/credential/owner/source switch cannot repaint old data. Read APIs/UI do not POST commands, repair manifests or start capture/batches. Extend AST boundaries, stable schema pins and feature-off V1/V2 gates. Re-run `tests/unit/test_observer_population_replay.py`: optional new service/cursor composition must preserve bare FastAPI persistence attachment without settings, normal observer/replay attachment, and production lifespan with roots unset or unavailable. Test through real app attachment, not a hand-built fake service map.
### Required Interfaces and Contracts
No new runner/result/replay/codec/observer protocol version, command/event, metric family or SQL migration. Existing scientific fingerprints and objective events remain unchanged by read-only access. Charts/graphs have accessible tables, focus/keyboard affordances, reduced-motion-friendly graph transitions and responsive layout (desktop wide and narrow fallback).
### Requirement Evidence
Original request coverage matrix in index; project regression/authority rules; real artifact reconciliation requirement.
### Error Handling and Logging
Test both safe log metadata and absence of payload/credential strings. Optional prerequisites unavailable → report UNEXECUTED with reason, not pass. Do not disable coverage, skip import gates or relabel controlled data as scientific proof.
### Tests
Run client full suite/check/build, targeted Python API/architecture and compatibility suites, pinned Godot protocol suite; run compose only with explicit available Docker/browser/image prerequisites. Full commands below.
### Acceptance Criteria
All nineteen features and seven focus dimensions have behavioral evidence with at least one populated case; lifecycle/capture-off remains usable and explicit. New-read access leaves stored artifacts/history unchanged.
### Verification
From repository root:
```sh
pnpm --dir clients/research-ui check
pnpm --dir clients/research-ui test
pnpm --dir clients/research-ui build
uv run --frozen --python 3.12.14 ruff check src tests
uv run --frozen --python 3.12.14 mypy src
uv run --frozen --python 3.12.14 lint-imports
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/architecture tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py tests/unit/test_research_ui_state.py tests/unit/test_research_matrix_fs.py tests/unit/test_research_cultural_api.py tests/unit/test_semantic_history_api.py tests/unit/test_semantic_history_projection.py tests/unit/test_observer_population_replay.py tests/unit/test_observer_demographic_api.py tests/unit/test_lineage_api.py tests/unit/test_civilization_overlay_api.py tests/unit/test_benchmark_research_ui_artifacts.py -q
"${GODOT_BIN}" --headless --editor --path clients/godot-observer --quit
"${GODOT_BIN}" --headless --path clients/godot-observer --script res://tests/run_protocol.gd
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term -m compose tests/compose/test_generational_research_ui_browser.py -q
```
Use Godot4.7.2 pin and existing published-image environment/fixture setup. Integration database work, if the browser harness needs it, is restricted to a validated disposable `palimpsest_test` database. Do not infer database authorization from a production DSN.

## Task 24: Complete mandatory documentation and final requirements verification
### Intent
Ship a truthful researcher guide and a reproducible handoff, not just components.
### Implementation Steps
1. Run `$aif-docs` as the mandatory documentation checkpoint. Extend Research UI guide with grouped screen map, nineteen-feature source/evidence table, marker-discovery H versus view T, composite cohort identity versus generation navigation, sparse sampling, exact/evidence-anchor boundaries, budgets, private checkpoints and capture prerequisites. Keep README as landing/index only.
2. Research API docs specify three cultural endpoints plus retained semantic history, auth, schemas, windows, resource bounds, nested `rows_json` validation, runtime completion/binding versus legacy exports, cursor errors and no backfill/restart guarantee. Explain structural/digest read validation versus trusted scientific verification. Godot guide gives working seven-focus links with source-specific institution/technology examples, separate identity/scope owners, publication resolution and known unavailable cases. Do not advertise unsupported lineage publication query parameters or subjective institution-lineage scope.
3. Development docs record unit/mounted/browser/Godot commands, required artifacts/storage roots and how real BL output differs from constructed presentation fixtures. Document no new capture switches/runner schema/migration/metric family and default behavior unchanged.
4. Verify all original request rows against implementation/tests, check new files follow public boundaries, and record executed versus unexecuted gates with exact failures in plan progress notes. Invoke `$aif-verify` against this explicit bundle after implementation; do not close M7 wholesale because institutional economy/kinship handoff remain open.
### Required Interfaces and Contracts
Documentation must name actual supported APIs and limitations. Screens that require missing capture must be documented as unavailable, not advertised as reconstructing old private state. Do not edit unrelated historical counts/requirements just to make documents look consistent.
### Requirement Evidence
User accepted tests/verbose safe logging/mandatory docs/M7 linkage; project docs ownership and roadmap rules.
### Error Handling and Logging
No secrets, real credential examples or absolute private storage paths in docs/screenshots. If any requirement lacks a populated behavioral proof, leave completion blocked and state which source/test is missing.
### Tests
Review all documented command/route names against code and execute available documentation/link checks from project tooling. Manually validate example links with the shared fixture contract. No blanket documentation scan required.
### Acceptance Criteria
Docs checkpoint complete; original scope reconciled; verification honestly reports optional missing prerequisites; only this plan's progress is closed when justified.
### Verification
`pnpm --dir clients/research-ui check`; shared TS/Python/Godot link tests; `$aif-verify @.ai-factory/plans/v3-42-generational-research-ui/index.md` after implementation. Expected result: all mandatory gates pass, optional external gates explicitly accounted for.

## Phase Risks and Mitigations
Browser fixtures may overstate science: label provenance and keep real BL API proof separate. Large scope can tempt superficial panels: populated behavioral assertions and index requirement matrix are completion gates.

## Phase Completion Checklist
All tasks meet acceptance, docs checkpoint and final verification are recorded; checkboxes stay exclusively in index.
