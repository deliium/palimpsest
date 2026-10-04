# Godot observer

[← Read-only observer](observer.md) · [Research API](research-api.md) · [Back to README](../README.md)

The Godot observer is a read-only 2D presentation of a running world. It lives in `clients/godot-observer/` and is not a Python package. Simulation code does not import it. The published API serves the already-exported files at `/` and does not import the client.

Opening the client, moving the camera, or changing playback speed does not change seeds, event ids, or `exact_trajectory_hash`.

## Target

Reference editor and export binary: Godot 4.7.2 stable. The project is 2D, GL Compatibility (`gl_compatibility` on desktop and mobile). The committed export preset is Web, with thread support off. The client uses `HTTPRequest` and `WebSocketPeer` only.

## What it reads

HTTP GET only:

- `/v1/simulations/{run_id}/observer/manifest`
- `/v1/simulations/{run_id}/observer/state`
- `/v1/simulations/{run_id}/observer/events` with optional `agent_id`, `event_type`, `location_id` (and resume cursors)
- `/v1/simulations/{run_id}/observer/run`
- `/v1/simulations/{run_id}/observer/ticks`
- `/v1/simulations/{run_id}/branches` / `branch` / `branch/fork-point` (lineage GETs; `objective_inspection`)
- `/v1/simulations/{run_id}/observer/agents/{agent_id}/labels` (SUBJECTIVE perspective; `subjective_debug`)
- `/v1/simulations/{run_id}/observer/agents/{agent_id}/relationships` (SUBJECTIVE; `subjective_debug`)
- `/v1/simulations/{run_id}/observer/agents/{agent_id}/narrative-hops` (SUBJECTIVE ledger hops; `subjective_debug`)
- `/v1/simulations/{run_id}/observer/communication-strategy-audit` (ANALYTICAL research/debug; `subjective_debug`)
- `/v1/simulations/{run_id}/debugger/events/{event_id}/causal-trace` (research causal debugger; `subjective_debug`)
- `/v1/simulations/{run_id}/debugger/causal-trace?tick=&sequence=` (alternate address; `subjective_debug`)
- `/v1/simulations/{run_id}/metrics` then `/metrics/{metric_set_id}/{family}` (ANALYTICAL catalog discovery; `objective_inspection`)

It also opens `/v1/simulations/{run_id}/observer/stream` and never sends a text or binary WebSocket payload. Protocol `observer-protocol-v1` is required. A different `protocol_version` is shown as `unsupported_observer_protocol` and is not applied.

Manifest and run envelopes always carry `run_id`. Optional fork fields (`parent_run_id`, `fork_tick`, `intervention_summary`, `branch_id`) appear on research branch children only — unknown keys are ignored. Branch navigation replaces the active `ObserverSource` (close stream, clear world/log/timeline marks, bootstrap the other `run_id`). There is **no** dual-world viewport or simultaneous fold of two runs in the client. The client never creates forks (`POST .../branches`) from Godot.

## Evidence classes

Every researcher overlay marker carries exactly one class: **OBJECTIVE**, **SUBJECTIVE**, or **ANALYTICAL**. The overlay legend (default off) toggles researcher layers and shows those badges. Inferred groups, norms, conventions, reputation aggregates, and strategy categories never paint as objective zone ownership.

## V2 physical visuals

The client parses `world.structures` and paints kind / integrity / stored-quantity cues at location anchors. Production semantic types (`RESOURCE_HARVESTED`, `CRAFT_STARTED`, `ITEM_CRAFTED`, `STRUCTURE_BUILT`, `STRUCTURE_REPAIRED`, `ITEM_STORED`) have dedicated effect actions and log phrases. Tool-like item kinds use local theme mapping. Season / weather / band / hazard / depleted paints come from frame refresh; scarcity outlines use objective quantity (`0` depleted; soft scarce cue for small positive quantities).

## Perspective limits

Selected-agent perspective loads only SUBJECTIVE projections: labels, relationships, territorial claims, and narrative-ledger hops when toggled. `GET .../agents/{id}/observation` returns counts-only (`AgentVisibleOut`) and is not used as a known-artifact payload. Clearing perspective removes SUBJECTIVE layers. ANALYTICAL overlays stay independent researcher toggles.

## Communication ordinary vs research

Ordinary speech bubbles show semantic type + other agent id, optionally `declared_confidence_band`, with distinct styles for talk / ask / tell. They never show deception or other audit categories even when the research payload is loaded. Opt-in `communication_strategy_audit` (ANALYTICAL) may show per-event research categories beside the event id; aggregate `communication_strategy@1` rates are summary-only via metric catalog discovery.

## Narrative hops vs lineage metric

Alice→Bob→Carol hops come from the SUBJECTIVE narrative-ledger projection (`carrier_agent_ids`, locations, parents, opaque event ids). A SUBJECTIVE narrative selector picks a variant id; the event log marks matching `source_event_id` / `last_communication_id` lines already in the loaded window. No content tokens or fingerprints as labels. `cultural_narrative_lineage@1` is ANALYTICAL aggregate detectors only and must not invent speaker order.

## Metric catalog discovery

Analytical overlays call `GET .../metrics`, pick the newest catalog entry that lists the family, then `GET .../metrics/{metric_set_id}/{family}`. Empty catalog or missing family → empty overlay + `overlay_unavailable`.

## Performance

At high speed (`>= 8x` or dense pending motions) the client snaps motion, coalesces trivial same-entity activity marks, caps concurrent speech bubbles, and skips nonessential pulses while keeping reducer state correct.

An optional perspective control can fetch SUBJECTIVE layers for one agent; primary captions keep researcher identity. The client does not reconstruct memories, beliefs, goals, emotions, or utterance text locally. Causal explanation uses the server debugger payload only (see [Research causal debugger](research-causal-debugger.md)).

## Causal debugger

Select an event log line and press **Why?** to `GET` the causal-trace route with the session token header. Godot is render + navigate only: it never assembles causality, invents stages, or shows private CoT / prompts / utterance / memory / belief text. Presentation labels live in the client (`debugger_labels.gd`) and must not be read as chain-of-thought. Multi-graph analysis and matrices live in the [Research UI](research-ui.md) (`/research/`), not this panel.

Outbound **Research UI** navigation uses `ResearchUiLink` (`scripts/protocol/research_ui_link.gd`): Web opens via `JavaScriptBridge`, desktop via `OS.shell_open`, logging `research_ui_link_opened`. The Why? panel exposes a **Research UI** button (`view=traces`). Research UI may embed the Observer in a same-origin iframe and falls back to a new tab on bootstrap failure — no shared mutable store.

HTTP `403` / missing `subjective_debug` uses the same `overlay_unavailable` pattern as narrative overlays — never an empty chain presented as “no cognition”.

### Compact strip (default)

The inspector opens compact: eight researcher-facing cells with locked status rollup over their child wire nodes (`available` wins; else `truncated` → `failed` → `skipped` → `unavailable`, with one contributing `reason_code`):

| Compact | Wire `stage_code` sources |
| --- | --- |
| Observed | `observation` |
| Remembered | `relevant_memories`, `reconstruction` |
| Believed | `beliefs`, `theory_of_mind` |
| Felt | `emotional_state` |
| Wanted | `goals` |
| Expected | `imagined_futures`, `counterfactuals` |
| Decided | `selected_intention` |
| Acted | `action` |

Supporting nodes (`situation_model`, `budget_summary`) stay secondary — never in the compact strip.

**Expected** chrome: use artifact kind `counterfactual` when any Expected child is a non-`unavailable` `counterfactuals` stage, or when CF id_refs / selection codes (`counterfactual` / `cf_*`) appear; otherwise `imagination`.

Header shows `availability`, `ambiguity`, `address.agent_id`, tick/sequence/`event_id` — not a raw wire dump.

### Expanded artifacts

**Expand** reveals the full ordered researcher chain in server `RESEARCHER_CHAIN_SEQUENCE` order (**Emotion before Goals**):

Observation → Memories → Reconstructed memory → Beliefs → Emotion → Goals → Theory of Mind → Imagined futures → Counterfactuals → Intention → Action

Rows show status, counts, command/intention codes, and id-ref counts only.

### Artifact-kind chrome

Closed presentation kinds distinguish objective vs subjective content so imagination/counterfactual rows never look like world facts: `objective_event`, `observation`, `memory`, `belief`, `imagination`, `counterfactual`, `analytical_inference`. Legend copy marks non-objective kinds as structured artifacts, not ground truth.

### Seek vs Provenance

Dual affordances — never combined in one click:

1. **Seek** (Seek button or activate a row with `observer_focus`) — seek `(tick, sequence)` / highlight `event_id`; panel stays open; primary causal-trace payload stays stashed.
2. **Provenance** (Provenance button, or right-click shortcut, when a mapped `id_ref` exists) — `GET …/debugger/lineage/{kind}/{id}?owner_id=…` with `owner_id` from `address.agent_id` only (never guessed from display names). Unmapped wire kinds WARN `unmapped_debugger_id_ref` and skip. Missing `owner_id` WARNs `owner_id_missing` and skips. Secondary pane lists entry id / status / optional `observer_focus` only.

| Wire `id_ref` kind | Lineage `kind` |
| --- | --- |
| `memory` | `memory_derivation` |
| `belief` / `semantic_belief` | `belief_evidence` |
| `goal` | `goal_ancestry` |
| prediction / CF subject ids | `prediction` |

**Back** / return-to-decision pops a navigation stack (depth ≤8) and restores the stashed primary payload, clearing the secondary pane.

Metadata-only logs (examples): `why_requested`, `debugger_opened`, `seek_from_debugger`, `debugger_nav_push`, `debugger_return_to_decision`, `owner_id_missing`.

Deep-link / web query params (credential-free; UI “event N” = `sequence`):

| Param | Required | Notes |
| --- | --- | --- |
| `run_id` | yes | Starts the session |
| `tick` | for event focus | Non-negative int |
| `event_id` / `event` | preferred | Opaque id |
| `sequence` | with tick when known | Intra-tick sequence |
| `agent_id` / `agent` | optional | Perspective hint |
| `debugger` | optional | `1` / `causal` opens the debugger after seek |

Query keys such as `token` / `api_key` are rejected (`query_string_secret`).

## Same-origin setup

URL code joins an origin string and a path. On a Web export the origin is `window.location.origin`, and `GET /version` fills the status strip. Off Web, a configured `palimpsest/observer_origin` loads that origin's `/version`. With no origin the strip uses the protocol constant `observer-protocol-v1`, the export engine `4.7.2-stable`, the application version from `build-info.json` when the export wrote it, and revision `unknown`.

The four status lines are application version, protocol, export engine, and backend revision. A bad manifest, frame, or known event shows `unsupported_observer_protocol` and is not applied. The log line is `[observer.protocol] parse_failed reason_code=unsupported_observer_protocol`.

`./run.sh` prints `INFO startup_ready url=http://127.0.0.1:8080/`. On a Web export, `/?run_id=<id>` fills the run field and starts the session. Optional deep-link params (`tick`, `sequence` / `event_id`, `debugger`) seek and may open the causal debugger after bootstrap — see [Causal debugger](#causal-debugger). The log is `[observer.session] web_run_id_applied run_id=<id>`. The query never carries a token. A URL with no query, or an empty `run_id`, waits for Connect.

Scripts under `clients/godot-observer/scripts/` do not contain a loopback host. There is no second reverse proxy: `/health`, `/version`, `/v1`, and the observer WebSocket stay on the same origin as `index.html`.

## Local token

The HTTP header is `x-palimpsest-token`. The WebSocket subprotocols are `palimpsest.v1` and `palimpsest.token.<token>`. The token is never placed in the query string.

Put a local token in gitignored `clients/godot-observer/override.cfg`:

```ini
[palimpsest]

api_token="replace-me"
observer_origin="https://observer.example"
run_id="run-1"
```

Do not commit that file. `project.godot` leaves `api_token` empty.

## Run id and fixture playback

The run id comes from the field at the top of the window or from `palimpsest/run_id`. Connect loads the manifest, then the current state, then the stream. Folded `frame.events` are history already in `world`. They are not tweened and they are not copied into the live event log.

**Play fixture** applies `clients/godot-observer/fixtures/smoke/reference_session.json` through the same reducer and views. It does not open a socket. V2 coverage stubs live under `fixtures/smoke/v2_mechanics.json` (structures, production events, catalog-miss / narrative-hop / strategy-audit stubs).

## Timeline controls

The playback row is read-only. None of these controls pause, step, or reseed the simulation, and none of them change the run.

| Control | Effect |
| --- | --- |
| Play | While replaying, step forward through committed events. While live, resume applying events that were held during pause. |
| Pause | Stop playback locally. A live run keeps committing. The socket stays open. |
| Previous Event / Next Event | Move one committed `(tick, sequence)`. They do not wrap at the first or latest event. |
| Previous Tick / Next Tick | Land on the last event of the neighboring tick that has events. |
| Jump to Tick | `GET .../state?tick=` for the start of that tick, and focus the first event of that tick when the log page contains it. |
| Jump to Event | `GET .../state?tick=&through_sequence=` for that committed event. |
| Return to Live | Drop the replay buffer, load the unscoped state, and open the socket at the head cursor. |
| `0.25x` `0.5x` `1x` `2x` `4x` `8x` `16x` | Local tween speed only. Slower than `1x` lengthens motion and speech. `8x` and `16x` step a whole tick and skip tweens. Changing speed does not seek and is not sent to the server. |

Going backward requests a reconstructed frame. It does not play a reverse tween.

Status chrome always shows `LIVE` or `REPLAY` (plus paused / behind live when applicable), and distinct `loading` / `seeking` / `switching_run` copy while bootstrap or seek work is in flight. Protocol mismatch keeps reason `unsupported_observer_protocol` and names expected `observer-protocol-v1`.

### Keyboard shortcuts

Shortcuts use InputMap / `_unhandled_input` and do not fire while a text field has focus:

| Key | Action |
| --- | --- |
| Space | Play / pause (local) |
| ← / → | Previous / next event |
| Shift+← / Shift+→ | Previous / next tick |
| L | Return to live |
| F | Toggle follow on the current focus target |
| B | Bookmark the viewed tick |
| `[` / `]` | Previous / next focused event |
| Esc | Clear follow / selection where safe |

## Branch navigation

The branch panel shows the current `run_id`, optional parent / fork tick / intervention summary / `branch_id`, and a paged child list from `GET .../branches` (`after_child_run_id` when `next_cursor` is present). Root runs without lineage show an empty state, not an error. Missing `objective_inspection` surfaces a capability reason code.

| Control | Effect |
| --- | --- |
| Open parent at fork point | `GET .../branch/fork-point`, then clean `switch_run(parent)` and seek to `parent_observer_tick` |
| Open child | `switch_run(child)`; optional seek to that child's fork tick |
| Return to previous run | Pop a session-only stack (depth ≤16) of `{run_id, tick, sequence}` and restore that source |

Each switch tears down the stream, cancels HTTP seeks (queue clear + request epoch), clears world layers / log / timeline marks (not bookmark files), and bootstraps one new source. No occupancy or log lines merge across runs.

## Event log

The log is one bounded page, near 200 lines, replaced on each seek. A line is `tick:sequence type actor target description`. The subject is `target_id` for `AGENT_DIED`, `NEEDS_APPLIED`, and `EXPOSURE_APPLIED`, and `actor_id` otherwise. Labels prefer `agent_id`, then the raw id. Location names prefer `display_name`, then `name`. Clicking a line seeks that event. **Why?** requests the research causal debugger for the selected line. Utterance text is not printed.

Three filters hide loaded lines and do not request another route:

- agent: actor, target, or label
- event type: exact semantic type
- location: origin, destination, or location name

Empty filters show every loaded line.

Selecting an agent (entity id from `world.agents`) or location can also refresh the window via `GET .../events?agent_id=` / `location_id=`. Server-side `agent_id` matches **actor or target** after adapt (so Alice as death/help target is included). Client substring filters remain a secondary aid on the loaded page. Next / previous focused event prefer neighbors inside that window, then bounded GETs / probes (no full-journal reverse scan).

## Focus and follow

Agent focus and location focus may combine in the log filter. **Follow** is mutually exclusive (one camera/UI target): it recenters via `camera_rig.focus_on` only. Follow never pauses the run, never calls simulation control / admission / fork routes, and never changes seeds or event ids. Clearing selection or turning Follow off stops tracking only.

## Timeline markers

The bar shows the viewed event tick and the live tick from `GET .../observer/run`. Configurable category toggles (ProjectSettings / local config) paint marks for death, attack, major weather/environment, artifact creation, structure creation, and synthetic **branch_point** ticks from lineage. Birth stays empty until a birth-class semantic type exists in the protocol — roster presence is not invented as birth.

Loading strategy: paint first from the bounded log window; optional enrichment runs at most one refresh with ≤3 sequential `event_type` pages; drawn marks cap at 64 (DEBUG when truncated). The client does not scan the whole journal. Clicking a mark seeks that event (branch points use tick-start `state?tick=`).

## Local bookmarks

Researcher bookmarks are **observer metadata only** — not authoritative simulation history. They are never written into journals, snapshots, manifests, evidence exports, or branch lineage.

- Store: `user://observer_bookmarks/<safe_stem>.json` where `safe_stem` is a filesystem-safe encoding of `run_id` (slug + short hash). The JSON body always includes the original `run_id`.
- Fields: `tick`, optional `sequence`, `note`, `created_at_utc` (wall clock for researcher notes — never simulation time).
- UI: add / edit / delete / jump (jump seeks like Jump to Tick/Event).
- Web/HTML5: Godot `user://` persistence; private/incognito sessions may drop bookmarks. No server bookmark API.

## Pause and behind live

Pause does not pause the run. New live events sit in a buffer of at most 256 and are not applied until Play. Event 257 discards that buffer. The status bar shows `behind live` until Return to Live or a successful catch-up. The same status is shown when the viewed event is behind the run head. Return to Live ignores the buffer, reloads the head, and resumes the socket.

A completed seek logs in this shape, with no token:

```text
[observer.session] seek_applied mode=REPLAY tick=4 sequence=1
```

## V2 graphical benchmark fixture

Deterministic `observer-graphical-v2` (see [V2 benchmark suite](v2-benchmark-suite.md)) exercises multi-location movement, resources, communication, exchange, environmental dynamics, production, a terminal event, artifacts, and social transmission. Fixture JSON: `clients/godot-observer/fixtures/observer_graphical_v2.json`. Protocol coverage gap-fills pause/seek/return-to-live/filters/follow/debugger/fork switch without rewriting working controls. Presentation seek/pause must not change simulation outcomes.

Normal researchers use the prebuilt Web export via `./run.sh` — not the Godot editor. Zero-install acceptance is Docker/container + browser only.

## Headless checks

Godot protocol tests are outside default pytest. Pytest only checks that the golden JSON still constructs `observer-protocol-v1` values and that the smoke file's unknown type is outside the closed semantic list.

```bash
godot --headless --path clients/godot-observer --script res://tests/run_protocol.gd
```

## Logging

`palimpsest/log_level` defaults to `DEBUG` and can be set to `WARN` for a web export without a code edit. Lines look like `[observer.session] bootstrap_ready tick=2`.

These fields stay out of logs:

- token
- seed
- utterance text

Coordinates are not logged at INFO. Relationship scores are not shown or logged.
