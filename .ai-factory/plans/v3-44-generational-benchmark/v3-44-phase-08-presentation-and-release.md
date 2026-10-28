# Phase 8: Populated client acceptance and zero-install release

Plan: [index.md](index.md)
Tasks: 17–20
Depends on: Tasks 1–16

## Objective

Validate a real multi-generation history in Godot and populated research evidence in the SPA, shipped in the normal image. End users need a container runtime and browser only; developers/CI may use pinned compilers and browser drivers.

## Current-Code Evidence

| Path | Symbols / sections | Why it matters |
| --- | --- | --- |
| `clients/godot-observer/tests/run_protocol.gd` | `SUITES` | Explicit registry of all pinned protocol/view tests |
| `clients/godot-observer/tests/test_generational_navigation.gd` | `_generation_timeline` | Marker rendering is not a full replay workflow |
| `clients/godot-observer/tests/test_civilization_playback.gd` | seek/stale/capture-off cases | Existing bounded playback oracle |
| `clients/research-ui/src/research/acceptance.test.ts` | `populated panel acceptance` | Currently all fetches return unavailable; not populated acceptance |
| `clients/research-ui/src/views/ForkComparePanel.svelte` | `runCompare`, `openObserver`, `openResearch` | Untested fork comparison workflow |
| `Dockerfile:61–77` | runtime stage | Ships Godot assets but no Research UI |
| `compose.yaml` | image-only services | Normal pull/run path must stay image-only |
| `tests/compose/conftest.py` | `_generational_stack`, `GenerationalStack` | Test-owned authenticated image stack |
| `.github/workflows/observer-image.yml` | browser smoke and release publish | Current browser job omits civilization/Research UI suites |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/experiments/civilization_benchmark_visual.py` | create | One bounded real replay recipe and evidence markers |
| `clients/godot-observer/tests/test_multigeneration_replay.gd` | create | Coherent cross-surface replay tests |
| `clients/godot-observer/tests/run_protocol.gd` | modify | Register new suite |
| `clients/research-ui/src/research/acceptance.test.ts` | modify | Keep unavailable tests and add truly populated responses |
| `clients/research-ui/src/views/ForkComparePanel.test.ts` | create | Parent/child selection and comparison tests |
| `Dockerfile`, `compose.yaml`, `.dockerignore` | modify | SPA build stage/runtime assets; preserve image-only startup |
| `clients/research-ui/package.json` | modify | Pin package manager used in container build |
| `tests/compose/conftest.py`, `tests/compose/test_generational_research_ui_browser.py` | modify | Self-contained authenticated populated stack/workflows |
| `tests/compose/test_research_ui_wiring.py` | modify | Image-backed/authenticated SPA and real V2 matrix checks; no host-dist prerequisite |
| `tests/compose/start_v3_benchmark.py`, `tests/compose/test_v3_benchmark_release.py` | create | Real benchmark production and browser/image acceptance |
| `.github/workflows/observer-image.yml` | modify | Mandatory complete acceptance before release publication |

## Task 17: Replay one real multi-generation visual fixture in Godot

### Intent

Prove one coherent history contains and presents all eight requested phenomena, not a montage of unrelated unit fixtures or a screenshot-only startup check.

### Implementation Steps

1. Implement `build_v3_visual_benchmark(seed=23)` using the Phase 1 visual budget (160 ticks, six founders, cap 16). Include two regions, explicit lifecycle/init, developmental/cultural/knowledge/experimentation, projects and subjective-office prerequisites; use the new blank learner pack for entrants. Keep it a separately labeled controlled integration fixture, not one of the 30 autonomous research findings.
2. Version a bounded opportunity schedule: initial firsthand activity/experimentation and local communication; entrant teaching; project contributions; regional journey/re-contact; repeated independent role-directed communication/activity; lifespan turnover and later role-claim evidence. Refer to actual created IDs, actual addressed recipients and observed roles; no direct ledger injection or globally appointed successor. All effective commands are recorded and ordinarily admitted. Use two local exposure contexts for cultural differentiation; never preseed culture packs.
3. Publish objective, cultural, lineage and civilization evidence through production publishers. Export an acceptance marker manifest with qualified source references and exact seek boundaries for new agents, deaths, migration, teaching, project activity, technology spread, cultural differentiation and subjective office succession. Select markers from actual evidence; a missing marker is a failed visual-fixture coverage gate, not an invented event. No seed hunting, unlimited retries or forced world institutions to fill a marker.
4. Add Godot tests driving real session/controller/view surfaces through forward playback, pause, backwards seek, generation jumps, stale-response rejection and parent/child run switches. Compare objective demographic state with frame cursor and source-pinned analytical overlays. Ensure owner/subjective/analytical chrome stays visible for role/culture/technology data.
5. Test capture-off/partial/forbidden states separately and prove no client request advances ticks or sends mutation commands. If a view defect is found, limit changes to the owning existing session/view file and add a regression; do not change protocol or simulation semantics to make the display convenient.

### Required Interfaces and Contracts

Visual markers are presentation-test metadata, not observer semantic types or simulation inputs. Office succession is an owner-local belief transition, not proof of a global office. A missing real succession/differentiation trajectory blocks that positive visualization acceptance claim; autonomous null research still remains valid. Policy-fixture rendering tests may be synthetic but cannot substitute for this real-run gate.

### Requirement Evidence

Original Request — Visualization acceptance (all eight items), Godot read-only and coordinate invariants; `docs/observer.md`; `docs/long-horizon-scalability.md` — browser evidence distinct from backend timing.

### Error Handling and Logging

Surface stale/forbidden/unavailable evidence honestly; do not substitute another snapshot. Log bounded marker/count/status metadata only. Failing marker coverage reports its selector and missing channel, not private content.

### Tests and Verification

With `GODOT_BIN` pointing to checksum-pinned 4.7.2-stable from `clients/godot-observer/export/pins.env`:

```bash
"${GODOT_BIN}" --headless --editor --path clients/godot-observer --quit
"${GODOT_BIN}" --headless --path clients/godot-observer --script res://tests/run_protocol.gd
```

Task 20 supplies real-browser visual evidence. Capture before/after authoritative high-water hashes to prove seeking/playback did not mutate science. Do not overwrite the three preexisting untracked research-focus `.uid` files.

Producer invocation: `uv run --frozen --python 3.12.14 palimpsest-matrix civilization-benchmark run --profile visual --lane mechanism --output /tmp/opencode/v3-44/visual --timeout-seconds 300 --code-revision "$PALIMPSEST_V3_SOURCE_REVISION" --source-artifact-digest "$PALIMPSEST_V3_SOURCE_ARTIFACT_DIGEST"`. Supply verified source values as described in Phase 9, or use a verified clean-source assertion instead of the digest. This resolves only `v3-visual-integration-v1`, not the 30 research cases; Task 20's in-container producer uses the same dispatcher contract.

### Acceptance Criteria

Pinned suite passes and the real fixture contains all eight source-backed markers. Browser acceptance later demonstrates that the shipped Web client can inspect them.

## Task 18: Inspect populated evidence and fork history in the Research UI

### Intent

Panel headings and 404 responses are not evidence that researchers can inspect the requested histories.

### Implementation Steps

1. Rename current unavailable-only acceptance grouping accurately and retain it as negative-state coverage. Add valid populated response fixtures for genealogy, qualified knowledge/technology lineage, cultural traits, narratives, institutions, migration, demographics and fork lineage. Fixture contents are rendering tests, explicitly not scientific findings.
2. Add `ForkComparePanel.test.ts`: fetch actual parent/child lineage and comparison metadata, choose two children, show comparison/coverage, navigate back to parent and open observer/research links. Verify no credential enters query strings, history state or storage.
3. Test cross-panel tick/generation/owner/window selection, actual back and forward navigation, reload, pages including empty continuation, stale requests, run switches and cleared credentials. Assert qualified rows/edges and evidence-class labels, not only headings.
4. For real browser acceptance, use Phase 2/6 producer artifacts and existing GET APIs. Include real populated data for the nine requested domains; absence/partial/forbidden are separate tests. Do not publish fake lineage or bypass credentials to fill UI rows.

### Required Interfaces and Contracts

Nine acceptance domains are genealogy, knowledge lineage, technology history, cultural evolution, historical narratives, institutions, migration, population and forked historical runs. Existing view names/routes stay unchanged. Objective data requires inspection, private/analytical data retains subjective-debug policy. No new write route or client capture authority.

### Requirement Evidence

Original Request — Research UI acceptance; `src/api` existing generational read services; `clients/research-ui/src/api/research.ts` — demographic/generation/lineage readers. Do not treat debug credentials as normal public access.

### Error Handling and Logging

Unknown, complete-empty, scan-limited, forbidden and unavailable stay distinct. Browser console never prints tokens, payloads or raw fetch errors. Test failures identify panel/selector/status only.

### Tests and Verification

```bash
pnpm --dir clients/research-ui test
pnpm --dir clients/research-ui check
pnpm --dir clients/research-ui build
```

Test populated and negative evidence, actual `go_back()`/`go_forward()`, fork navigation and credential-free focus links. Task 20 verifies shipped-image browser behavior without a host frontend build.

### Acceptance Criteria

All nine domains have populated component and genuine production-backed browser evidence; missing source history remains honestly unavailable.

## Task 19: Ship both Web clients in the normal release image

### Intent

Preserve end-user zero-install operation for Godot and eliminate the Research UI manual-build gap.

### Implementation Steps

1. Add a `research-ui-build` Docker stage using Node 24 LTS, pinned to an exact published version and immutable digest at implementation time. Pin pnpm to an exact compatible version in `packageManager` and install it inside this stage. Record chosen pins in the implementation evidence; floating `latest` is forbidden. Reuse the committed pnpm lock; do not inspect its full contents or regenerate dependency versions without need.
2. Copy only SPA source/build inputs and run frozen dependency installation plus `pnpm build`. Copy the built file tree to `/app/share/research-web`, owned by the existing non-root runtime user. Set `PALIMPSEST_RESEARCH_WEB_ROOT=/app/share/research-web` alongside the existing Godot root. Runtime gets no Node, pnpm, Godot editor or export templates.
3. Preserve API mount order `/research/` before Godot `/`, correct asset content types, history fallback and `GET /version` engine/revision identity. Add/extend static-serving tests through discovery of the existing static route tests, not a second router.
4. Keep base Compose image-only: pull/migrate/API startup must not require host build tools or asset volumes. Update comments/help for both browser entrypoints. Retain opt-in development overrides separately. Scope `.dockerignore` changes to include needed first-party source and exclude node_modules/generated output.
5. Verify clean-container startup with only image/Compose and standard configuration. Download/build tools are CI/image-build dependencies, not end-user prerequisites. Do not put acceptance credentials in the release image or enable subjective debug by default. Add build arguments `PALIMPSEST_SOURCE_CLEAN` (default false) and `PALIMPSEST_SOURCE_ARTIFACT_DIGEST` (default empty) alongside existing `PALIMPSEST_REVISION`. Validate a nonempty revision and exactly one true clean assertion or canonical source digest before accepting qualification metadata. Store these attestations in image labels `org.opencontainers.image.revision`, `io.palimpsest.source-clean` and `io.palimpsest.source-artifact-digest`; they are build/test metadata, not new application settings. CI must verify the source assertion before passing it; a revision/build success alone does not prove clean source. The benchmark producer extracts labels and passes Task 5's explicit CLI arguments, without needing Git in the image or inventing source cleanliness.

### Required Interfaces and Contracts

No new environment prefix, image runtime privilege or API version. Existing `PALIMPSEST_RESEARCH_WEB_ROOT` is reused. Normal users use a published image and browser; no local Godot/editor, manual Web export, manual frontend build, host Node/pnpm/Python or test harness is required. Exact base-image/package-manager pins are a mechanical supply-chain resolution, not an unresolved architecture choice.

### Requirement Evidence

Original Request — zero-install deployment and Visualization acceptance; `Dockerfile`; `compose.yaml`; `.ai-factory/ARCHITECTURE.md` — Python never imports clients and static mount order.

### Error Handling and Logging

Image build fails on frozen-lock mismatch, checksum failure, missing expected assets or unsupported engine identity. Log tool/version/stage/status only; never dump environment, expanded Compose configuration or credentials. Health failure blocks release.

### Tests and Verification

```bash
docker build --tag palimpsest-api:v3-44 \
  --build-arg PALIMPSEST_REVISION="$PALIMPSEST_V3_SOURCE_REVISION" \
  --build-arg PALIMPSEST_SOURCE_ARTIFACT_DIGEST="$PALIMPSEST_V3_SOURCE_ARTIFACT_DIGEST" .
```

Use verified source values from Phase 9; a verified clean checkout may instead pass `--build-arg PALIMPSEST_SOURCE_CLEAN=true` and omit the digest. Do not claim the currently dirty working tree is clean merely because `git rev-parse HEAD` returns a commit. Use Task 20's isolated Compose fixture to check `/`, Godot JS/WASM/PCK, `/research/`, hashed SPA JS/CSS, deep route fallback, `/health` and `/version`. Inspect source labels and runtime executable availability through container tests: no editor/templates/Node compiler toolchain. No host asset mount is allowed in the release path.

### Acceptance Criteria

One release image serves both clients and starts with a container runtime alone. The original Godot export remains checksum-pinned and runs only in the build stage.

## Task 20: Gate release on authenticated real-browser benchmark acceptance

### Intent

Turn missing browser prerequisites into visible unexecuted gates and prevent release publication on a skipped or heading-only check.

### Implementation Steps

1. Extend test-owned `GenerationalStack` fixture with benchmark output roots, a matrix output root and both client paths. Launch a unique Compose project with database name containing `palimpsest_test`, temporary credentials and isolated storage. Run `start_v3_benchmark.py` inside the built application image via Compose to generate the visual history, required populated case histories and grouped children using production repositories/publishers. Extract the explicit source attestations from image labels and forward Task 5's CLI arguments unchanged; missing/invalid/conflicting labels fail required acceptance. Also execute the existing `tests/fixtures/matrices/v2-benchmark-suite.json` through the production matrix executor/aggregator to create its real `matrix-metric-summary-v1` artifact in the test-owned matrix root. Mount that root read-only at the API's configured `PALIMPSEST_RESEARCH_MATRIX_ROOT`. Do not insert synthetic world/lineage/metric-summary rows into the acceptance stack.
2. Replace external-URL-only research smoke dependence with this shared stack in release tests. Explicitly refactor `tests/compose/test_research_ui_wiring.py`: remove the local `DIST/index.html` prerequisite from the release SPA check, request `/research/` from the shipped image, and use the shared stack plus inspection credential for the V2 matrix GET. Assert the real matrix sidecar is present; 404/auth failure in required mode is failure, not skip. Keep first-party static configuration/fixture checks. Existing optional externally supplied smoke mode can remain an explicitly separate local convenience, but it must not determine required release results. Authenticate through headers/subprotocols and the existing client credential mechanism, never query strings.
3. In Playwright open the actual exported Godot app; seek every Task 17 marker, verify corresponding UI/view state and evidence classes, step backward/forward and switch parent/child. Save bounded screenshots and source-linked assertion receipts. For canvas-only elements, use existing test-safe read-only telemetry hooks; any new hook exposes only view state and never mutation authority.
4. Open `/research/`, assert real populated rows/edges in all nine domains, actual historical tick/back/forward/reload, parent/child comparisons and credential-free Godot links. Deny inspection/debug in negative cases and confirm absence of leaked private data. Compare durable high-water before/after all read workflows.
5. Add required-mode handling to the new release test: missing image/runtime/browser/data is an error in CI, while local optional suites may skip with explicit reports. Update `observer-image.yml` to run existing V2, generational, civilization and Research UI browser tests plus the new benchmark suite before publishing images/archives. Assert required tests were collected and zero required skips occurred; retain redacted failure artifacts and clean only the unique test project/volumes in fixture teardown.

### Required Interfaces and Contracts

Production capture is opt-in for fixture generation; ordinary deployment still defaults off. Scientific execution status and browser/publisher readiness are independent. A real visual-history marker missing from the actual run blocks that acceptance claim; a fake screenshot or mocked API must not replace it. Manual browser review supplements, not substitutes for, the automated gate.

### Requirement Evidence

Original Request — Visualization and Research UI acceptance; `tests/compose/test_observer_generational_browser.py` — distinguishes API generation execution from browser layout fixtures; existing V3-43 browser gate was unexecuted, not certified.

### Error Handling and Logging

Timeout, missing data, forbidden source and browser console failure have safe codes. Missing host `clients/research-ui/dist` must not affect release acceptance; missing image assets, matrix sidecar or valid image source identity must fail required checks. Redact stack failures, HTTP headers and screenshots containing credentials. CI stores bounded screenshots and manifest/status summaries, never recordings or subjective payload dumps. No expanded Compose config logs.

### Tests and Verification

```bash
PALIMPSEST_API_IMAGE=palimpsest-api:v3-44 PALIMPSEST_V3_ACCEPTANCE_REQUIRED=1 \
uv run --frozen --python 3.12.14 pytest --cov --cov-report=term -m compose \
  tests/compose/test_stack.py \
  tests/compose/test_observer_browser.py \
  tests/compose/test_observer_generational_browser.py \
  tests/compose/test_observer_civilization_browser.py \
  tests/compose/test_generational_research_ui_browser.py \
  tests/compose/test_research_ui_wiring.py \
  tests/compose/test_v3_benchmark_release.py -q
```

`PALIMPSEST_V3_ACCEPTANCE_REQUIRED` is a proposed test-harness-only switch, not an application setting or runner field. CI uses the same behavior and inspects the required-test report.

### Acceptance Criteria

Both shipped clients inspect actual benchmark evidence without host Godot/frontend tooling. Required browser suites execute without skips before release publication, and read workflows do not alter authoritative history.

## Phase Risks and Mitigations

- A positive visual fixture can be confused with an emergence result: label controlled intervention receipts and evidence classes throughout.
- A Web canvas can render while backend evidence is missing: assert marker source identities and rendered state together.
- Preexisting `.uid` files are user work: never reset/delete/overwrite them during implementation or tests.

## Phase Completion Checklist

- Verify Tasks 17–20; update index only.
- Missing browser/image prerequisites block acceptance, not permission to run network-free work.
