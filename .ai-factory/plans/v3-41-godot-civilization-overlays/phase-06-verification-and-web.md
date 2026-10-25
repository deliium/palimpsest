# Phase 6: Security, browser release and documentation

Plan: [index.md](index.md)  
Tasks: 16–18  
Depends on: Tasks 1–15

## Objective

Prove authority/privacy/history invariants and actual exported-browser usability while preserving the existing zero-install published-image workflow.

## Current-Code Evidence

| Path | Symbols / responsibility | Consequence |
|---|---|---|
| `clients/godot-observer/export/pins.env` | pinned editor/templates | Preserve exact `4.7.2-stable` and SHA512 pins. |
| `clients/godot-observer/project.godot`, `export_presets.cfg` | Compatibility, nonthreaded Web | No desktop-only APIs, threads or native extensions. |
| `Dockerfile`, `scripts/export-observer-web.sh` | build-stage export, static runtime tree | Researchers never need local Godot; runtime has no editor. |
| `tests/compose/test_observer_browser.py`, `test_observer_generational_browser.py` | published-image browser harness | Exercise actual WASM/UI, not only headless/native fixtures. |
| `tests/architecture/test_observer_isolation.py`, `test_godot_client_isolation.py`, `test_lineage_explorer_boundaries.py` | package/authority gates | Add new read-model/capture boundaries without widening domain imports. |
| `tests/benchmarks/test_observer_scale_scenarios.py` | opt-in scale patterns | Existing nonnegative timing assertions are not latency budgets. |

## Files to Change

Create `tests/architecture/test_civilization_overlay_boundaries.py`, `tests/compose/test_observer_civilization_browser.py`, `tests/benchmarks/test_civilization_playback.py`, `docs/godot-civilization-overlays.md`.

Extend `tests/compose/conftest.py`, relevant new unit/client tests, `tests/unit/test_observer_export_pins.py` only for unchanged pin assertions, `docs/observer.md`, `docs/godot-observer.md`, `docs/development.md`, `docs/configuration.md`, `README.md` documentation index. Test the exact `compose.civilization.yaml` introduced in Task6; do not change `Dockerfile`, ordinary `compose.yaml`, engine pins or runtime build/install behavior for a host read-only mount that an override already supplies.

## Task 16: Enforce authority, privacy and compatibility gates

### Intent

Prevent presentation enrichment from expanding simulation authority, exposing private histories or changing established version contracts.

### Implementation Steps

1. Add AST/import tests: simulation/API/persistence do not import analysis/experiments for these read paths; only trusted experiments/research composition calls calculators/publishers. Reader and publisher capabilities are distinct; API routes are GET-only and cannot write/repair/capture. Domain stays framework-free; clients remain unimported by Python.
2. Add privacy canaries to producer/response/log fixtures: memory text, record marks, belief prose, private messages, prompts and credentials are absent from objective outputs and all logs. Private analytical catalogue/counts are authorization-gated before reads. Revoke debug with requests in flight and verify all owner-level state clears.
3. Add noninterference comparisons of captures off/on/failing across representative legacy and V3 runs: event bytes/order, commands, RNG/stochastic identity, stop reason, subjective checkpoint and replay scene match. GET map/overlay/marker requests must leave run revision, event high water, files and control state unchanged.
4. Verify untouched compatibility pins: default runner v4/result v2, latest feature runner v55, selected replay-v22/codec v20, commands43, observer semantics73, metrics136, Alembic0017, `/v1`, `observer-protocol-v1`, `observer-layout-v1`. New sidecar IDs/settings do not imply accepted core version changes.
5. Test all supported selector combinations in the manifest, including full-prefix boundary normalization, private prefix rejection, missing exact capture, sparse continuation, corruption, expired publication and wrong world/config/revision identity. Assert physical I/O and decoded-row budgets, nested-detail truncation versus scientific coverage, digest-DAG verification, event cadence/recovery completeness and cumulative institution sample normalization. Explicitly test existing generic metric-origin fallback is not used for civilization nonspatial rows. Cover actual production execution hooks and each completion/skip/adoption path; sidecar failure must never delete scientific completion or cause a completed run to rerun.

### Requirement Evidence

Architecture/rules — authority, owner scope, default-off versions; Original Request — clear evidence and correct history. Existing sources refine the request; no exception allows inferred social labels into objective state.

### Error Handling and Logging

Tests assert closed safe reason codes and redact payload-bearing exceptions. Do not weaken coverage, architecture allowlists or strict models to make the suite pass. Distinguish pre-existing dirty-tree failures from regressions without reverting user edits.

### Tests and Verification

```bash
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_observer_civilization.py tests/unit/test_observer_civilization_api.py tests/unit/test_civilization_capture.py tests/unit/test_civilization_publication.py tests/unit/test_civilization_filesystem.py tests/unit/test_civilization_cli.py tests/unit/test_civilization_overlay_api.py tests/unit/test_civilization_markers_api.py tests/unit/test_civilization_fixtures.py tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py tests/architecture -q
uv run --frozen --python 3.12.14 ruff check src tests
uv run --frozen --python 3.12.14 mypy src
uv run --frozen --python 3.12.14 lint-imports
```

### Acceptance Criteria

All new/gating tests pass without disabled coverage or widened trust exceptions. Existing observer/generational suites remain green. Record actual failures/prerequisites honestly; test command inclusion is not evidence of execution.

## Task 17: Prove exported-browser playback and bounded resource use

### Intent

Validate the delivered Web observer, including high-speed behavior, not just native parsers or HTTP availability.

### Implementation Steps

1. Extend the published-image Compose/Playwright harness using the actual `compose.civilization.yaml` override and Task15 run/publications, same disposable PostgreSQL database, read-only `/civilization` bind, configured cursor key, and independent inspection/debug credentials entered through memory-only UI. Assert all observer navigation/fetch requests are GET; run setup is a separate producer. Verify a publication is browsable without manual image rebuild/config editing, the API UID cannot write the mount, and plain root-off `./run.sh` behavior remains unchanged.
2. Assert actual rendered map/panel outcomes through the existing fixture/debug bridge or an equivalent metadata-only test hook disabled outside test mode: two settlement candidates, correct regional placement and journey arrival, project/public-good/repository states, analytical culture denominator, attributed technology edge, scoped group and institution badges, and unplaced institution without origin marker. Do not treat network JSON success as rendered visual proof. Screenshots may supplement, not replace, model/UI assertions.
3. Play real256-tick history at1×/8×/16×, pause at a common final cursor, wait/explicitly refresh the same enabled scopes, and compare accepted objective/semantic digests. Rebuild both clients at a shared paused LOD before comparing draw-plan identities/counts; intentionally different fast glyph/label layouts are not semantic failures. Scrub across arrival/acquisition/confirmed institution-transition fixtures. Use separately labeled constructed pack for positives absent in the real run. Add delayed-sidecar tests proving at least three intermediate matching map/overlay bundles display during forward play, plus deadline/missing-layer/pause behavior. Fast view has no animation backlog, starvation, stale private overlays or future markers.
4. Browser performance guard on fixed CI Chromium, 1280×720, software-rendered Compatibility export: warmed-up control-to-visible busy/paused feedback p95 <=250ms measured over20 local interactions; final-state adoption <=2s after its local fixture HTTP response; <=2 civilization requests in flight, <=32 transient effects, <=400 flow segments/800 glyphs, <=32MiB civilization cache and no monotonic node/cache growth after50 seek cycles. Test a synthetic dense render pack separately (2,000 rows) and disclose it as a rendering load fixture, not a scientific long run. Network/DB latency is recorded separately, not hidden inside the UI budget.
5. Test capture-off, debug-disabled, forbidden, missing boundary, partial/cap, corrupted/expired publication and failed optional-service cases in actual browser. Base objective replay and zero-install startup must remain usable. Switching run/branch/owner/credentials while a response is delayed must not flash old private data.
6. Verify published image includes HTML/JS/WASM/PCK, `application/wasm`, `/version` engine/protocol metadata, WS hello and nonempty map; no runtime editor process or browser dependence on local editor/export. Preserve `run.sh` pull/run and `/research/` mount before root. Validate nonthreaded Web with no COOP/COEP or native-extension prerequisite added by overlays.

### Requirement Evidence

Original Request — high-speed correctness and zero-install Web; `docs/development.md` — pinned export/browser acceptance; Task 15 — real versus constructed evidence provenance. Release readiness requires an actual built image and matching pinned templates.

### Error Handling and Logging

Collect bounded network statuses, safe state digests in test reports only, counts, timing and screenshots without credentials/private payload. Runtime logs still exclude content fingerprints; test equality digests are not production logging. Missing Docker/editor/templates/browser/image/database prerequisites are explicit unexecuted blockers, never skipped-as-pass release claims.

### Tests and Verification

```bash
"${GODOT_BIN}" --headless --editor --path clients/godot-observer --quit
"${GODOT_BIN}" --headless --path clients/godot-observer --script res://tests/run_protocol.gd
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_observer_export_pins.py tests/unit/test_godot_observer_fixtures.py tests/unit/test_godot_protocol_mirror.py -q
PALIMPSEST_API_IMAGE=<built-image> uv run --frozen --python 3.12.14 pytest --cov --cov-report=term -m compose tests/compose/test_observer_browser.py tests/compose/test_observer_generational_browser.py tests/compose/test_observer_civilization_browser.py -q
PALIMPSEST_TEST_DATABASE_URL=<disposable-palimpsest_test-url> uv run --frozen --python 3.12.14 pytest --cov --cov-report=term -m "integration and scale" tests/benchmarks/test_civilization_playback.py -q
```

`<...>` values are operator-supplied prerequisites, not literal shell values. Build a contributor image through existing `run-dev.sh`/Docker export workflow when needed; researchers still run the published image via `./run.sh`.

### Acceptance Criteria

Real Chromium/WASM tests prove rendered state, history equivalence, request/resource limits and unchanged zero-install deployment. Timing budgets pass on the declared reference job; flaky thresholds are investigated, not removed or silently relaxed.

## Task 18: Document evidence semantics and complete the release handoff

### Intent

Researchers can enable/read overlays correctly and reproduce browser acceptance without installing Godot or assuming captured history exists.

### Implementation Steps

1. Invoke mandatory `$aif-docs` checkpoint. Write `docs/godot-civilization-overlays.md` with physical versus inferred category table, settlement heuristic, exchange-versus-transfer semantics, culture denominators/partitions, knowledge-versus-capability distinction, owner groups, institution grounding/unplaced rules and missing-capture interpretation.
2. Document exact GET sidecars/selectors/cursors, availability/error states, layer/evidence supported combinations, default-off capture/CLI flags, durable same-database prerequisites and actual optional deployment: set `PALIMPSEST_CIVILIZATION_HOST_ROOT`, persistent `PALIMPSEST_CIVILIZATION_CURSOR_KEY`, inspection/debug capabilities, then `docker compose -f compose.yaml -f compose.civilization.yaml up -d --wait` using the existing image. Explain producer-only writable host access and API read-only mount. Plain `./run.sh` remains the root-off zero-install baseline. Examples use environment placeholders, never secrets in URLs/output. Existing persisted metrics permissions are unchanged; new owner-level/inferred layers use debug.
3. Explain capture-before-run, finished-run publication, independent event versus snapshot cadence coverage, recovery gaps/quotas/no-backfill/resume/fork limits, separate scientific completion versus publication readiness, all skip/adoption safeguards, archived data not being a subjective restart, explicit recorded-boundary playback, prefix/full-boundary semantics,2second automatic-presentation wait and high-speed LOD. State that culture frequencies are analytical overlays, never terrain; missing/timed-out layers are not zero or disappearance.
4. Update observer/configuration/development pages and README links narrowly; replace stale limitations only for implemented behavior. Preserve historical version notes instead of globally replacing old counts. M7 linkage does not close M7 or claim ownership of `institutional_economy`/kinship handoff/M6 testimony.
5. Publish compact verification handoff: changed surfaces, exact tested image/revision/pins, commands/results, real versus constructed fixture provenance, resource/timing measurements and any unexecuted release gate. No commit/push/deploy without user authorization. Update Task18 only after documentation and verification agree with executable behavior.

### Required Interfaces and Requirement Evidence

Original Request — zero-install browser and epistemic clarity; architecture — documentation/roadmap ownership; config — Docs yes. User instructions and plan define feature intent; docs describe implemented reality rather than authorizing extra features.

### Error Handling and Logging

Examples contain placeholders, never tokens or credential URLs. Document safe codes and likely remedies without encouraging capture backfill or API write mounts. Documentation work itself needs no new runtime logs; verification output remains bounded and redacted.

### Tests and Verification

Check every new relative Markdown link, new flag against `uv run --frozen --python 3.12.14 palimpsest-matrix --help` and relevant subcommand help, route/setting names against tests. Re-run fixture/export pin tests and browser acceptance when examples/deployment defaults change. Use the docs skill's existing validation workflow; do not introduce a new docs toolchain for this feature.

### Acceptance Criteria

Documentation clearly distinguishes available, missing and inferred history, provides a no-local-Godot researcher workflow and an explicit contributor verification workflow, and links all new pages. Handoff reports actual tests rather than planned commands as passes.

## Phase Risks and Completion

Browser prerequisites may be unavailable in an agent environment: partial implementation may be reported, but release readiness cannot be asserted without browser/image proof. Respect existing dirty changes throughout. Update Tasks 16–18 only in `index.md` after verified completion.
