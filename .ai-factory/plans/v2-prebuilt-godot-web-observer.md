# Implementation Plan: Prebuilt Godot Web Observer

Branch: main
Created: 2026-09-28
Improved: 2026-09-28 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete milestone; this plan packages the existing read-only observer for startup without a local Godot install and does not claim `advanced_social_inference`, `multi_hop_testimony_tracking`, or any new capability flag.

## Compatibility contract

This plan changes how the existing observer is built and served. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants stay intact. `WorldEngine` remains the only objective mutation authority. The client still reads observer HTTP GET routes and the observer WebSocket. It never calls simulation control or any other mutating route.
2. No new capability flag. No `V2CapabilityFlags` slot, no `runner-config` bump, and no Alembic revision.
3. V1 regression gate stays green under flags-off and tracing-off. The client is not an experiment arm and must not be appended to `tests/unit/test_v1_regression_gate.py`.
4. No schema bump of authoritative history and no change to `observer-protocol-v1` or `observer-layout-v1`.
5. No scripted emergence. Serving the canvas does not add graph edges, roles, or milestone scripts.
6. No LLM involvement.
7. Experiments stay reproducible. Opening the page, connecting, moving the camera, or changing playback speed must not change seeds, event ids, or `exact_trajectory_hash`.
8. Optional cognition tracing stays outside the client. Do not request cognition-trace rows, memories, beliefs, goals, emotions, or utterance text.
9. `src/` still must not import `clients/godot-observer` or contain the substring `godot`. The API serves an already-exported file tree from a configured directory. That reverses the previous observer plan's exclusion of FastAPI hosting, and it does not make the client a Python package.

## Goal

A researcher starts the published stack with Docker and a browser. Normal startup does not install Godot, open the editor, install export templates, run `godot --export-release`, compile the visualization, or copy Web export files.

Primary path, matching the current published API port:

```bash
./run.sh
```

Then open `http://127.0.0.1:8080/` (`PALIMPSEST_API_PUBLISH_PORT` when set). `docker compose up -d` on `compose.yaml` is the same pull-and-start path and must not require `--build`.

Contributors who change Godot sources use `./run-dev.sh`, which is the only normal local build. They do not edit export presets in the editor. The committed Web preset is the preset CI and the dev image use.

## Decisions

- **Serving.** FastAPI serves the generated files (option A). There is no second reverse proxy. `/health`, `/version`, `/v1`, and the observer WebSocket stay on the same origin as `index.html`, so the Web client keeps using `window.location.origin`. Threads stay off, so the server does not add COOP/COEP isolation headers.
- **Where Godot runs.** Godot 4.7.2 stable exists only in the image export stage and in the export CI job. The runtime image contains the exported files and the Python API. It does not contain the editor or the template archive.
- **Compose files.** `compose.yaml` references a published image and has no `build` key. `compose.dev.yaml` is explicit and is not named `compose.override.yaml`, because Compose would load an override automatically and turn `docker compose up` into a local build. `run-dev.sh` passes `-f compose.yaml -f compose.dev.yaml`.
- **Image pin.** One variable, the full reference: `image: ${PALIMPSEST_API_IMAGE:-ghcr.io/deliium/palimpsest:0.1.0}`, matching `pyproject.toml` `version`. No `latest` tag. The release workflow also pushes the full git SHA. Publishing happens on a `v*` tag, not on pull requests. Smoke tests set `PALIMPSEST_API_IMAGE` to the locally tagged build and start Compose with `--pull never`.
- **Until the first tag exists.** `./run.sh` fails with a message that the release image is not published and that `./run-dev.sh` is the contributor path. It still must not fall back to a local Godot build.
- **Credentials.** The published Compose stack leaves `PALIMPSEST_API_AUTH_REQUIRED` unset, which is the current open-local default. The Web build keeps `palimpsest/api_token` empty. Turning credentials on stays the existing header and WebSocket-subprotocol path and is not required to open the page.
- **Example world.** Smoke tests encode `build_reference_scenario(...).config` with `encode_runner_config`, post that payload with the bundle fingerprint and schema version, then start and tick until `GET .../observer/manifest` lists `loc-camp`. They do not add a simulation shortcut inside the client. On a Web export, `?run_id=` starts that session. The query never carries a token.
- **Default pytest.** Ordinary unit tests do not launch Docker or Godot. Browser and image checks are `compose` tests and CI jobs. `pytest` already excludes `compose`.

## Commit Plan

- **Commit 1** (after tasks 1–3): `feat(observer): bake a pinned Godot web export and serve it from the API`
- **Commit 2** (after tasks 4–6): `feat(observer): show versions, accept a run id query, and start from the published image`
- **Commit 3** (after tasks 7–10): `test(observer): prove the prebuilt client and document Godot-free startup`

Each checkpoint is a git commit on `main` created when those tasks are done. Do not squash them into one commit at the end. `git.create_branches` is false, so implementation stays on the current branch.

## Tasks

### Phase 1: Pinned Export

- [x] Task 1: Pin Godot 4.7.2 and export the committed Web preset headlessly.
  - Deliverable: Add `clients/godot-observer/export/pins.env` with `GODOT_VERSION=4.7.2-stable`, the official non-C# URLs `https://github.com/godotengine/godot/releases/download/4.7.2-stable/Godot_v4.7.2-stable_linux.x86_64.zip` and `https://github.com/godotengine/godot/releases/download/4.7.2-stable/Godot_v4.7.2-stable_export_templates.tpz`, and SHA-512 pins taken from the release `SHA512-SUMS.txt`: `9aa00f7a605200940bce3027a567b782f49bd8e940dd06ae9e987bd65aee1b1467edd56ed84fcdcbdd44354bf613bdbb4e5d2913e925850368e150c59ed54c65` for the Linux zip and `ca4d71c4d7b81dfc15d1a98baa07534aa95b03fdda78a0075b06672e1648d2e5f40980c9adc28d23e1b92e732ee7bf3461997aa804af74ec2fcd7a93ccb84079` for the templates. Add `scripts/export-observer-web.sh`. It sets a writable `HOME` before the download, downloads those two files, and checks SHA-512 before unzip. After unzip it finds `Godot_v4.7.2-stable_linux.x86_64`, marks that binary executable, and copies the unpacked `templates/` directory to `$HOME/.local/share/godot/export_templates/4.7.2.stable/`. It refuses to continue unless `<binary> --version` prints `4.7.2.stable`. It then runs that binary `--headless --path clients/godot-observer --import`, then `--headless --path clients/godot-observer --export-release "Web" <dest>/index.html`. It fails if `export_presets.cfg` is not platform `Web`, `variant/thread_support` is not false, or `project.godot` is not `gl_compatibility` / features `4.7` and `GL Compatibility`. It fails if a `.csproj` or C# section appears. It checks that `<dest>` contains `index.html`, `index.js`, `index.wasm`, and `index.pck`, and that `index.wasm` is non-trivial. It writes `<dest>/build-info.json` with `application_version` from `pyproject.toml`, `protocol_version` `observer-protocol-v1`, `export_engine` `4.7.2-stable`, `export_renderer` `gl_compatibility`, and `revision` from the caller. The script is for the container and CI, not for the user launcher. A unit test reads the preset and pin file and asserts those values. Do not point downloads at `latest`.
  - Logging: the script prints INFO lines `observer_export_download_ok file=%s bytes=%s`, `observer_export_version_ok version=%s`, `observer_export_started preset=Web`, and `observer_export_finished file_count=%s wasm_bytes=%s`. Checksum, version, or missing-file failures print ERROR `observer_export_failed reason_code=%s` and exit non-zero. Do not print the download bodies.
  - Files: `clients/godot-observer/export/pins.env`, `scripts/export-observer-web.sh`, `clients/godot-observer/export_presets.cfg`, `clients/godot-observer/project.godot`, `tests/unit/test_observer_export_pins.py`.

- [x] Task 2: Keep Godot out of the runtime image.
  - Deliverable: Extend `Dockerfile` with an `observer-export` stage and leave the last stage as the runtime. The export stage uses a digest-pinned Debian bookworm-slim base, installs only the shared libraries the official Linux editor needs, copies `pins.env` and `scripts/export-observer-web.sh`, and runs that script. It proves `<binary> --version` prints `4.7.2.stable` before `--import`. The runtime stage stays on the existing Python 3.12.14 slim digest, `uv sync --frozen --no-dev --no-editable`, and uid 1001. It `COPY --chown=palimpsest:palimpsest` only the export directory to `/app/share/observer-web` and sets `PALIMPSEST_PRESENTATION_WEB_ROOT=/app/share/observer-web` and `PALIMPSEST_REVISION` from a build arg. It does not copy the Godot binary, the zip, or the `.tpz`. `docker run` of the runtime image must show no `godot` executable and no `Godot_v4.7.2-stable` archive. `.dockerignore` already ignores `.github`; do not add `clients/godot-observer` itself to it. Do ignore `clients/godot-observer/override.cfg`, `clients/godot-observer/.godot/`, and `clients/godot-observer/build/` so a local token override or editor cache cannot enter the export. Local editor caches stay gitignored. A contributor extracts the files without opening the editor with `docker build --target observer-export --output type=local,dest=clients/godot-observer/build/web .`.
  - Logging: the export stage logs the script lines from task 1, including `observer_export_version_ok`. The runtime stage adds no Godot process. When the API later mounts the directory it logs from task 3.
  - Depends on task 1.
  - Files: `Dockerfile`, `.dockerignore`.

### Phase 2: Same-Origin Serving

- [x] Task 3: Serve the exported files from FastAPI and expose versions.
  - Deliverable: When `PALIMPSEST_PRESENTATION_WEB_ROOT` is an existing directory that contains `index.html`, mount it at `/` after every API and WebSocket router so `/health`, `/version`, and `/v1` win. Use static files with directory indexes off and `index.html` for `GET /`. `..` must not leave the export directory. If `index.html` is absent, skip the mount. An empty or missing root leaves the API unchanged, which is what `./scripts/api.sh` does on the host. Force content types `.html` → `text/html`, `.js` → `text/javascript`, `.wasm` → `application/wasm`, and `.pck` → `application/octet-stream`. Every other suffix uses the platform map so `.png` icons still load. Add `GET /version` returning JSON with `application_version` (the installed `palimpsest` distribution version), `protocol_version` (`OBSERVER_PROTOCOL_VERSION`), `export_engine` and `export_renderer` from `build-info.json` when that file is present, and `revision` from `PALIMPSEST_REVISION` or `build-info.json`. `GET /health` stays exactly `{"status":"ok"}`. If `build-info.json` `protocol_version` disagrees with `OBSERVER_PROTOCOL_VERSION`, log an error and still serve the files. Python source under `src/` must not contain `godot` or `clients/godot-observer`. Keep `tests/architecture/test_godot_client_isolation.py` green; extend it only if a new allowlisted filename is required, and do not allow the forbidden strings. No COOP/COEP headers.
  - Logging: INFO `presentation_static_mounted file_count=%s` once at startup. DEBUG `presentation_static_skipped reason_code=root_unset` when the directory is unset. ERROR `presentation_static_skipped reason_code=index_missing` when `index.html` is absent. WARN `presentation_static_missing path_suffix=%s` on a static 404, with the suffix only. ERROR `presentation_protocol_mismatch expected=%s baked=%s` when the baked protocol disagrees. Do not log tokens, query strings, or file bodies. `/version` logs INFO `route_version` with status and duration only.
  - Depends on task 2.
  - Files: `src/infrastructure/settings.py`, `src/api/app.py`, `src/api/presentation_static.py`, `src/api/routes/version.py`, `tests/unit/test_presentation_static.py`, `tests/architecture/test_godot_client_isolation.py`.

<!-- Commit checkpoint: tasks 1-3 -->

- [x] Task 4: Show versions in the observer and keep protocol mismatch visible.
  - Deliverable: On boot, the client shows four lines in the status area: application version, `observer-protocol-v1`, Godot export `4.7.2-stable`, and the backend revision. On a Web export it loads them from same-origin `GET /version`. Off Web, with an origin configured, it loads that origin's `/version`. With no origin it shows the GDScript protocol constant, the export-engine constant, application version from `build-info` when the export wrote it, and the backend line `unknown`. A mismatched or missing `protocol_version` on manifest, frame, or a known event still surfaces `unsupported_observer_protocol` in the status text and does not apply the payload. The headless protocol suite asserts that status text. Logs stay token-free. Do not put `localhost` or `127.0.0.1` in `clients/godot-observer/scripts/`.
  - Logging: INFO `[observer.version] version_loaded application=%s protocol=%s export_engine=%s revision=%s`. ERROR `[observer.version] version_failed reason_code=%s` when `/version` is unreachable. Existing `[observer.session]` and `[observer.protocol]` lines stay. The protocol failure stays `[observer.protocol] parse_failed reason_code=unsupported_observer_protocol` and the status detail includes that code.
  - Depends on task 3.
  - Files: `clients/godot-observer/scripts/ui/status_bar.gd`, `clients/godot-observer/scenes/ui/status_bar.tscn`, `clients/godot-observer/scripts/net/version_client.gd`, `clients/godot-observer/scripts/main.gd`, `clients/godot-observer/tests/test_models.gd`, `clients/godot-observer/tests/run_protocol.gd`.

- [x] Task 5: Start a Web session from the run id query.
  - Deliverable: On a Web export, read only the `run_id` query parameter via `window.location.search`. When it is non-empty, put it in the run field and start the session from `session.begin()`. A URL with no query, or an empty `run_id`, leaves the field blank and does not connect. Do not read a token from the query string. Do not put `localhost` or `127.0.0.1` in `clients/godot-observer/scripts/`. A headless test covers a present id, an empty id, and a URL with no query. Opening `/` in a browser still waits for Connect.
  - Logging: INFO `[observer.session] web_run_id_applied run_id=%s` when the query supplies an id. Do not log the rest of the URL. Existing `[observer.session] bootstrap_started run_id=%s` still follows a successful start.
  - Depends on task 4.
  - Files: `clients/godot-observer/scripts/net/session.gd`, `clients/godot-observer/scripts/net/origin.gd`, `clients/godot-observer/tests/test_web_run_id.gd`, `clients/godot-observer/tests/run_protocol.gd`.

### Phase 3: Normal Startup

- [x] Task 6: Start from the published image, and keep a separate developer build.
  - Deliverable: `compose.yaml` services `api` and `migrate` use `image: ${PALIMPSEST_API_IMAGE:-ghcr.io/deliium/palimpsest:0.1.0}` and have no `build` key. The database image pin is unchanged. `compose.dev.yaml` adds the local build, `network: host` on that build, and `PALIMPSEST_REVISION` from git when available. `./run.sh` checks that `docker` exists and that the daemon responds, runs `docker compose pull` of that image, then `docker compose up -d --wait --wait-timeout 180` with only `compose.yaml`. It refuses `--build`. It prints `Observer: http://127.0.0.1:<port>/` using `PALIMPSEST_API_PUBLISH_PORT` or 8080. `--open` launches the browser with `xdg-open` or `open` when one exists, and skips that step with a printed note when it does not. `./run.ps1` does the same checks and prints the URL; `-Open` uses `Start-Process`. Neither script installs Docker, Godot, or templates. Pull failure says the release image is unavailable and points at `./run-dev.sh`. Health-wait failure prints redacted service state and the API log tail, not `docker compose config`. `./run-dev.sh` is the one contributor command: `docker compose -f compose.yaml -f compose.dev.yaml up -d --build --wait --wait-timeout 180`. `./scripts/up.sh` stops passing `--build` and uses the same pull path as `./run.sh`. If someone passes `--build` to `up.sh`, the script exits with the `run-dev.sh` pointer and does not build. Smoke tests tag the locally built image and set `PALIMPSEST_API_IMAGE` to that tag, then start Compose with `--pull never` so the start does not pull or build.
  - Logging: INFO from the shell: `startup_docker_ok`, `startup_pull_started image=%s`, `startup_ready url=%s`. ERROR `startup_failed reason_code=%s` for missing docker, daemon down, pull failure, or health timeout. Do not print credentials or expanded Compose configuration.
  - Depends on task 2.
  - Files: `compose.yaml`, `compose.dev.yaml`, `run.sh`, `run.ps1`, `run-dev.sh`, `scripts/up.sh`.

<!-- Commit checkpoint: tasks 4-6 -->

- [x] Task 7: Lock the no-build startup in unit checks.
  - Deliverable: A unit test reads `compose.yaml` and asserts `api` and `migrate` interpolate `${PALIMPSEST_API_IMAGE:-ghcr.io/deliium/palimpsest:0.1.0}`, with no digest-less `latest` and no `build` key. It asserts `run.sh`, `run.ps1`, and `scripts/up.sh` do not invoke `godot`, `--export-release`, or `compose up --build`. It asserts `run-dev.sh` is the file that passes `compose.dev.yaml` and `--build`. Update `tests/compose/test_stack.py` so the config assertions match the image and the missing `build` key, and so the live stack fixture is not the only proof of a healthy published start. `GET /health` on a running stack stays `{"status":"ok"}`. The non-root uid 1001 assertion stays for the dev-built image when that compose test runs.
  - Logging: no production logger. Test DEBUG lines may record `compose_config_wait` as the existing compose tests do. Failed live checks still log `compose_smoke_failed` and redact secrets.
  - Depends on tasks 3 and 6.
  - Files: `tests/unit/test_published_startup.py`, `tests/compose/test_stack.py`, `tests/unit/test_presentation_static.py`.

### Phase 4: CI, Smoke, and Docs

- [x] Task 8: Build, smoke-test, and publish the ready-to-run image.
  - Deliverable: Add `.github/workflows/observer-image.yml`. On pull requests and pushes to `main`, the protocol job installs only the pinned editor zip from task 1, checks its SHA-512, and runs `Godot_v4.7.2-stable_linux.x86_64 --headless --path clients/godot-observer --script res://tests/run_protocol.gd`. That job does not download the template archive. The image job, whose runner does not install Godot, builds the Dockerfile from task 2 and does not run a second export outside that image build. It asserts the runtime image has no Godot binary, tags the build, sets `PALIMPSEST_API_IMAGE` to that tag, and starts `compose.yaml` with `--pull never` and no `--build`. The smoke checks `GET /` HTML, `index.js` as `text/javascript`, `index.wasm` as `application/wasm` with a non-trivial body, `index.pck` as `application/octet-stream`, and `GET /version` fields for application version, `observer-protocol-v1`, `4.7.2-stable`, and a revision. `tests/compose/start_reference.py` posts `encode_runner_config(build_reference_scenario(...).config)` with that bundle's fingerprint and schema version, then starts and ticks until `GET .../observer/manifest` lists `loc-camp`. It does not use the empty `runner-config-v2` body from `tests/integration/test_api_simulation_lifecycle.py`. The image job then runs the task 9 browser test. The job log for this start must not contain `godot --export-release`. Upload the web directory as a workflow artifact named `observer-web`. On a tag `v*`, push `ghcr.io/deliium/palimpsest:<version without v>` and `ghcr.io/deliium/palimpsest:<full sha>` to GHCR, and attach the web archive to the GitHub release. Do not push on pull requests. Pin third-party actions to commit SHAs. Do not use a floating Godot version.
  - Logging: workflow steps echo INFO `ci_export_ok wasm_bytes=%s` and `ci_smoke_ok url=%s`. Export or smoke failure is the step error. The API logs from tasks 3 and 4 appear in `docker compose logs` and must not include tokens. The workflow does not print `SHA512` file bodies beyond the verify line.
  - Depends on tasks 1, 2, 5, 6, and 7.
  - Files: `.github/workflows/observer-image.yml`, `tests/compose/start_reference.py`.

- [x] Task 9: Prove the browser checks against a stack that never builds Godot.
  - Deliverable: `tests/compose/test_observer_browser.py` is marked `compose` and is excluded from the default pytest run. Playwright stays out of the default `uv sync` group and is installed only in the CI smoke job. The test imports Playwright optionally and skips with a clear reason when Docker or Playwright is missing. When CI sets the locally built image as `PALIMPSEST_API_IMAGE`, it runs `docker compose up -d --wait --pull never` without `--build`. It checks the asset content types from task 8. Playwright opens `/?run_id=<id>` with software WebGL2, waits for the console line `[observer.locations] map_built location_count=4`, a non-null `webgl2` context on the canvas, and a WebSocket to `/observer/stream` that receives `hello`. It asserts the API container process list does not contain `godot`. A protocol-mismatch case is the headless GDScript test from task 8, not a second Python parser. The default `uv run pytest` command does not start the stack and does not download Godot.
  - Logging: DEBUG `observer_browser_wait url=%s` before navigation. ERROR `observer_browser_failed reason_code=%s` on timeout, plus the matching console lines, and no token. Compose teardown logs `compose_down project=%s` at DEBUG, matching `tests/compose/test_stack.py`.
  - Depends on tasks 5 and 8.
  - Files: `tests/compose/test_observer_browser.py`.

- [x] Task 10: Document the Godot-free startup path.
  - Deliverable: Route this checkpoint through `/aif-docs`. The primary README and `docs/development.md` quick start become `./run.sh`, then the observer URL on port 8080, with `docker compose up -d` as the equivalent. State that this path does not install Godot, open the editor, install export templates, export, or copy web files. Document `./run-dev.sh` and the `docker build --target observer-export` command as the contributor export. Document `?run_id=` as the Web auto-start and that the query never carries a token. Update `docs/godot-observer.md` so same-origin hosting is the API serving `/`, not a manual reverse proxy. Keep the read-only behavior, the empty committed token, and the headless protocol command as a contributor check that CI runs. Update the sentences in `.ai-factory/DESCRIPTION.md` and `.ai-factory/ARCHITECTURE.md` that say FastAPI does not serve the client: the API serves the prebuilt tree and still does not import it. Mention the version strip. Do not tell readers to run `docker compose up --build` for the normal path.
  - Logging: no new runtime logger. Docs quote the existing status and export log lines so operators can recognize `startup_ready`, `web_run_id_applied`, and `unsupported_observer_protocol`.
  - Depends on tasks 6 and 8.
  - Files: `README.md`, `docs/development.md`, `docs/godot-observer.md`, `docs/observer.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`.

<!-- Commit checkpoint: tasks 7-10 -->
