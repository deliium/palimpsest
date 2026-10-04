# Implementation Plan: Godot Observer Advanced Replay / Navigation

Branch: none (`git.create_branches=false`; current branch `main`)
Created: 2026-10-04
Improved: 2026-10-04 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete milestone; this plan completes researcher-facing replay/navigation on the existing Godot observer and branch APIs without claiming `multi_hop_testimony_tracking` or any new capability flag.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=auto
INFO [aif-plan] interpreted `ultra` as full mode (rich named plan); neither `fast` nor `full` was literal, matching prior v2 plan convention
INFO [aif-plan] plan name prefix v2- applied per user request; git.create_branches=false so stem is description slug
INFO [aif-plan] resolved plan file: .ai-factory/plans/v2-godot-observer-advanced-replay-navigation.md (format=slug)
INFO [aif-improve] applied refinement: URL allowlist + HTTP queue cancel; agent_id actor|target filter; reverse focus probe algorithm; marker fetch budget; clear_world on switch; bookmark path sanitization; Task 9 as integration suite; fix Task 4/5 dependencies

## Compatibility contract

This plan extends the read-only Godot observer client and thin GET wiring over already-shipped branch lineage and observer event filters. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants stay intact. `WorldEngine` remains the only objective mutation authority. Playback, follow, bookmarks, and branch switching never call simulation control, admission, fork-create, or any other mutating route from the observer UI.
2. No new capability flag. No `V2CapabilityFlags` slot, no `runner-config` bump, and no Alembic revision.
3. V1 regression gate stays green under flags-off and tracing-off. The client is not an experiment arm and must not be appended to `tests/unit/test_v1_regression_gate.py`.
4. Prefer no observer-protocol bump. Stay on `observer-protocol-v1` / `observer-layout-v1`. Reuse optional branch fields already on manifest/run and existing `GET .../observer/events` filters (`agent_id`, `event_type`, `location_id`). Branch navigation uses existing `GET .../branch`, `GET .../branches`, and `GET .../branch/fork-point` under `objective_inspection`. Additive presentation filter semantics for `agent_id` (actor **or** target) are allowed without a protocol rename.
5. No scripted emergence. Markers, labels, and shortcuts do not invent roles, graph edges, or milestone scripts.
6. No LLM involvement and no causal assembly in GDScript (debugger stays server-assembled).
7. Experiments stay reproducible. Switching runs, following an agent/location, seeking markers, and saving bookmarks must not change seeds, event ids, or `exact_trajectory_hash`. Follow is camera/UI focus only.
8. Bookmarks are observer metadata only. Persist separately from authoritative simulation history. Never write bookmarks into journals, snapshots, manifests, or branch lineage tables.
9. Respect long-experiment scale norms from `v2-long-experiment-scalability.md`: marker/focus GETs stay bounded; presentation may coalesce; scientific event pages and the observer journal path stay complete.

## Goal

A researcher can navigate committed history and research branches the way a debugger navigates call stacks — one clean `ObserverSource` at a time — with useful markers, agent/location focus, local bookmarks, and clearer connection/playback chrome, while keeping browser (Web) compatibility.

```text
branch panel / stack
  -> replace ObserverSource (close stream, clear world, bootstrap run_id)
  -> optional seek to fork tick

marker categories (configurable)
  -> filtered event pages + synthetic branch-point marks
  -> seek (tick, sequence)

select Alice / location
  -> filter + next/prev focused event
  -> Follow = camera/UI only

bookmarks (user:// keyed by run_id)
  -> tick + note; seek only; never mutate simulation
```

## Design Decisions (locked)

### Scope and ownership

- **Primary surface:** `clients/godot-observer/` presentation client, plus a minimal Python observer-events filter fix (Task 1b) so Alice-related pages include target-side events.
- **Reuse backend** for lineage and filtered events. Prefer client composition of existing single-`event_type` pages over a new marker aggregate route unless paging becomes unusable. No multi-type marker aggregate HTTP route in this plan.
- **No dual fold.** Never hold two worlds, two reducers, or two live streams. Branch compare stays the existing research API (`POST .../branches/compare`) and is out of Godot viewport scope for this plan.

### Transport / URL allowlist and HTTP cancellation

- Extend `ObserverUrls` query allowlist so focused and branch GETs can pass: `agent_id`, `event_type`, `location_id`, `after_child_run_id`, and debugger `sequence` (plus existing `limit`, `tick`, `layout_id`, `through_sequence`, `from_tick`, `to_tick`, and resume `after_tick`/`after_sequence`). Do not allow non-GET methods.
- `http_client.gd` gains `clear_queue()` (drop pending queue entries; in-flight completion is ignored via a request-generation / epoch counter on the session). `switch_run` and seek teardown must clear the queue and bump the epoch so stale branch/marker/focus responses cannot adopt into the new source.

### Clean ObserverSource replacement

When switching `run_id` (parent, child, return-to-previous, or Connect field):

1. Close the WebSocket with the existing client-stop path (no payloads).
2. Cancel in-flight seeks; bump seek serial **and** HTTP request epoch; `clear_queue()`; ignore stale HTTP responses.
3. Call an explicit `world_view` / UI **clear** path (clear tweens/motions, agent/location/object layers, overlays, event log window, timeline marks — **except** bookmark store on disk). Clear selection, follow target, perspective overlays, and transport LIVE/REPLAY cursor for the old run. Do not leave prior occupancy until the next frame arrives.
4. Reset session bootstrap flags (`_opened`, buffers, behind_live).
5. Set the new `run_id` and bootstrap via existing `manifest` → `state` → socket path.
6. Do **not** merge frames, occupancy, or log lines across runs.

Expose a single session API such as `switch_run(run_id, seek_tick=null, seek_sequence=null, push_history=true)` used by Connect and branch navigation. `start_with_run_id` must call the same teardown path (today it resets flags but does not define a full replace contract).

### Branch navigation UI

Show for the current run:

| Field | Source |
| --- | --- |
| current `run_id` | manifest / run |
| `parent_run_id` when present | optional fork fields |
| `fork_tick` when present | optional fork fields |
| `intervention_summary` / `branch_id` | optional fork fields |
| child branches | `GET /v1/simulations/{run_id}/branches` (paged via `after_child_run_id`) |

Allow:

- **Open parent at fork point** — `GET .../branch/fork-point`, then `switch_run(parent_run_id)` and seek to `parent_observer_tick` (tick-start / `state?tick=`).
- **Open child branch** — pick a child from the list; `switch_run(child_run_id)`; optionally seek to child fork tick.
- **Return to previous run** — client stack of `{run_id, tick, sequence}` pushed on each switch; pop restores previous source + cursor. Stack is observer-local memory (session), not server state.

Capability: branch GETs require `objective_inspection` (same token header as observer routes). Missing capability → clear empty-state / reason code, not a fake lineage tree.

### Timeline markers

Expand `timeline.gd` beyond death + selected-agent marks. Marker **categories** are configurable (toggles; defaults on for major objective events):

| Category | Semantic sources (closed) | Notes |
| --- | --- | --- |
| `birth` | birth-class type **if present** in protocol/event pages | No `AGENT_BORN` in `KNOWN_TYPES` today — category stays empty until such a type appears; do not invent births from roster presence |
| `death` | `AGENT_DIED` | Existing |
| `attack` | `AGENT_ATTACKED` | |
| `weather_environment` | `WEATHER_CHANGED`, `SEASON_CHANGED`, `TEMPERATURE_BAND_CHANGED`, `ENVIRONMENTAL_HAZARD_STARTED`, `ENVIRONMENTAL_HAZARD_ENDED`, `RESOURCE_NODE_DEPLETED`, `RESOURCE_NODE_RECOVERED` | Major env only; skip routine `NEEDS_APPLIED` / `EXPOSURE_APPLIED` / `RESOURCE_REGENERATED` |
| `artifact_creation` | `ARTIFACT_CREATED` | |
| `structure_creation` | `STRUCTURE_BUILT` | |
| `branch_point` | synthetic from lineage `fork_tick` (+ listed child fork ticks when loaded) | Not a world event; seek uses tick-start (`state?tick=`) |

**Loading strategy (locked):**

1. Paint first from the bounded events window already loaded for the log.
2. Optional enrichment: at most **one** marker refresh in flight; sequential per-type `GET .../events?event_type=…` with a shared budget of **≤3 type pages** per refresh; cancel on seek/`switch_run`.
3. Cap total drawn marks at **64**; DEBUG when truncated.
4. Do not scan the entire journal. Category config lives in client settings (ProjectSettings / local config), not server.

### Agent-focused playback

- **Select Alice** — existing agent click / inspector selection. Focus keys are **entity ids** resolved from `world.agents` (selection today uses `entity_id`). Display labels (`agent_id`) stay presentation-only and are not sent as the server filter value unless they equal the entity id.
- **Show Alice-related events** — drive event log filter; refresh the events window with `agent_id=<entity_id>` after Task 1b so the page includes events where that id is **actor or target** (not actor-only). Client substring filter remains a secondary UI aid on the loaded window.
- **Next / previous Alice event (locked algorithm):**
  1. Prefer neighbors inside the currently loaded focused/filtered lines.
  2. **Next** outside the window: `GET .../events` with filters + `after_tick`/`after_sequence` at the current view; take the first matching event; seek; do not invent events.
  3. **Previous** outside the window: walk candidates using existing `Transport.previous_event` + `GET .../ticks` helpers; for each candidate, accept only if it matches the focus filter (from the loaded window or a small probe page around that cursor). Bound probes at **32**; if none match, stop with empty-state `no_previous_focused_event`. Never invent events; never full-journal reverse scan.
- **Follow Alice** — keep camera on the selected agent's token via `camera_rig.focus_on` (and re-focus after seeks/live updates while follow is on). **Must not** change simulation behavior, pause the run, alter admission, or send any control API. Clearing selection or Follow off stops camera tracking only.

### Location-focused playback

- **Select location** — click location or pick from a compact control.
- **Show events in this location** — filter log by origin/destination/location; prefer `location_id=` on events GET when refreshing.
- **Follow location activity** — camera centers on the location anchor; optional auto-seek only when the researcher explicitly enables “snap to next location event” (default off). Follow remains presentation-only.
- Previous/next location-focused events reuse the same neighbor algorithm as agent focus, with the location filter.

Agent focus and location focus are mutually exclusive for Follow (one follow target). Filters may combine in the log (agent ∧ location ∧ type) when both are set without Follow conflict.

### Bookmarks

Local researcher bookmarks, examples:

```text
tick 1832 — strange attack
tick 4201 — rumor spread
```

- Store: `user://observer_bookmarks/<safe_stem>.json` where `safe_stem` is a filesystem-safe encoding of `run_id` (alphanumeric/hyphen slug + short hash suffix when needed). JSON body always includes the original `run_id` string. Fields: `tick`, optional `sequence`, `note`, `created_at_utc` (wall clock allowed for researcher metadata only — never used as simulation time).
- Web: rely on Godot HTML5 `user://` persistence; document that private/incognito may drop bookmarks. No server bookmark API in this plan.
- UI: add / edit / delete / jump. Jump seeks like Jump to Tick/Event.
- Bookmarks never appear in authoritative exports, evidence manifests, or branch lineage.

### Usability chrome (browser-compatible)

Improve without breaking Web export (no threads, no desktop-only dialogs required):

| Area | Behavior |
| --- | --- |
| Keyboard shortcuts | Space play/pause; ←/→ event step; Shift+←/→ tick step; L return live; F follow toggle; B bookmark at viewed tick; `[` / `]` focused prev/next; `Esc` clear follow/selection where safe. Register via InputMap / `_unhandled_input` without capturing text fields. |
| Loading indicators | Distinct `loading` / `seeking` / `switching_run` status; disable conflicting controls while switch/seek in flight. |
| Connection status | Surface socket connected / reconnecting / closed / capability failure with stable reason codes. |
| Live / replay indicator | Always-visible LIVE \| REPLAY (+ paused / behind live) from `transport`. |
| Protocol mismatch | Keep `unsupported_observer_protocol`; show human-readable empty-state copy naming expected `observer-protocol-v1`. |
| Empty states | No children, no markers in category, no agent events, no bookmarks — explicit messages, not blank panels. |
| Selected-agent inspector | Richer read-only snapshot: identity, location, life_status, measures, latest focused event description, follow state. Still no memories/beliefs/utterances. |
| Readable event descriptions | Extend `_describe` for env/artifact/structure clarity (location names, hazard/season/weather labels when fields exist on the event model). No utterance text. |

### Logging

GDScript stays `[observer.<area>] message key=value` with `palimpsest/log_level`. Python route/service logs stay on `infrastructure.logging.get_logger`.

- DEBUG: switch teardown steps, marker loads/truncation, focus neighbor probes, bookmark CRUD ids/ticks, shortcut actions, follow camera updates, `events_filtered` with `filter_codes`.
- INFO: run switch completed, mode LIVE/REPLAY, bookmark jump, open parent/child.
- ERROR: protocol mismatch, capability failure, switch/seek failures with reason codes only.
- Never log tokens, utterance text, bookmark note content at INFO (prefer `note_len` at DEBUG).

## Non-Goals

- Creating research forks from Godot (`POST .../branches`)
- Dual-branch compare viewport or simultaneous folds
- Server-persisted bookmarks or Alembic tables for observer metadata
- Server multi-type marker aggregate route
- Inventing birth events or scanning the full journal for marks
- Pausing/seeding/mutating the simulation from the client
- Protocol, runner-config, or capability-flag bumps
- Relationship/memory/belief/emotion inspectors beyond existing subjective overlays

## Commit Plan

- **Commit 1** (after tasks 1–1b): `feat(observer): allowlist focus queries and match agent actor|target`
- **Commit 2** (after tasks 2–3): `feat(godot): replace ObserverSource cleanly and navigate branches`
- **Commit 3** (after tasks 4–6): `feat(godot): add configurable timeline markers and focus playback`
- **Commit 4** (after tasks 7–8): `feat(godot): add local bookmarks and usability chrome`
- **Commit 5** (after tasks 9–10): `test(godot): cover advanced replay navigation and document controls`

Each checkpoint is a git commit on `main` when those tasks are done. Do not squash them into one commit at the end. `git.create_branches` is false, so implementation stays on the current branch.

## Tasks

### Phase 1: Transport, agent filter, clean switch, branches

- [x] Task 1: URL allowlist, HTTP queue cancel, and clean `ObserverSource` replacement.
  - Deliverable: (a) Extend `clients/godot-observer/scripts/protocol/urls.gd` allowlist with `agent_id`, `event_type`, `location_id`, `after_child_run_id`, and debugger `sequence` (keep existing keys). (b) Add `clear_queue()` on `http_client.gd` and a session request-generation/epoch so stale completions are ignored after switch/seek. (c) Add `switch_run(run_id, seek_tick=null, seek_sequence=null, push_history=true)` in `session.gd` that tears down stream, seeks, queue, epoch, transport cursor, selection/follow/perspective, and calls an explicit `world_view`/UI **clear** (motions, layers, overlays, event log, timeline marks — not bookmark files) before bootstrap. `start_with_run_id` and Connect use this path. Optional seek after bootstrap uses existing seek APIs once `_opened`. Focused unit tests: allowlist passes new keys; queue clear + epoch ignores stale; no cross-run occupancy/log lines after switch (fixture or mocked HTTP).
  - Logging: INFO `run_switched from_run_id=%s to_run_id=%s`; DEBUG teardown steps (`stream_closed`, `queue_cleared`, `world_cleared`, `cursor_reset`); ERROR on bootstrap failure with reason_code only.
  - Files: `clients/godot-observer/scripts/protocol/urls.gd`, `clients/godot-observer/scripts/net/http_client.gd`, `clients/godot-observer/scripts/net/session.gd`, `clients/godot-observer/scripts/view/world_view.gd` (clear hooks), UI clear hooks, `clients/godot-observer/tests/test_urls.gd`, `test_session_switch.gd` (or extend `test_session_cursor.gd`).

- [x] Task 1b: `agent_id` event filter matches actor **or** target.
  - Deliverable: In `src/api/observer_service.py` (and any persistence keyset helper used for `actor_id` alone), make `GET .../observer/events?agent_id=` return events where the id equals `actor_id` **or** `target_id` after adapt (presentation filter; no protocol bump). Today `actor_id=agent_id` drops target-only rows such as `AGENT_DIED`. Unit tests cover Alice as attacker and Alice as death/help target; unfiltered pages unchanged. Document the semantics in the route docstring / research-api note via Task 10.
  - Logging: existing DEBUG `events_filtered` with `filter_codes` including `agent_id`; add DEBUG `agent_match_mode=actor_or_target` once.
  - Depends on task 1 only for client allowlist readiness; Python change may land in the same commit as task 1.
  - Files: `src/api/observer_service.py`, persistence event keyset if needed for target index/filter, `tests/unit/test_observer_api.py` (or focused new module).

- [x] Task 2: Client run navigation stack (“return to previous run”).
  - Deliverable: Maintain a bounded stack (e.g. 16) of `{run_id, tick, sequence}` on switches when `push_history` is true. UI control **Return to previous run** pops and `switch_run` without pushing. Empty stack → empty-state message. Do not persist the stack across browser reloads in this plan (session-only). Focused unit test for push/pop/empty.
  - Logging: DEBUG `nav_stack_push/pop depth=%s run_id=%s`; INFO on successful return.
  - Depends on task 1.
  - Files: `session.gd`, `ui_layer.gd` / new branch panel script, tests.

- [x] Task 3: Branch metadata panel and open parent/child.
  - Deliverable: UI shows current run, parent (when present), fork tick, intervention summary, and paged children from `GET /v1/simulations/{run_id}/branches` using `after_child_run_id` when `next_cursor` is present. **Open parent at fork point** uses `GET .../branch/fork-point` then switch+seek to `parent_observer_tick`. **Open child** switches to selected child (optional seek to fork tick). Parse `BranchListOut` / `BranchForkPointOut` in a small protocol helper (unknown keys ignored). Root runs without lineage show empty-state, not errors. Capability failures surface reason codes. Focused parse/UI unit tests; full branch UX covered in Task 9.
  - Logging: DEBUG `branch_children_loaded count=%s`; INFO `branch_open_parent` / `branch_open_child` with ids and fork_tick.
  - Depends on tasks 1–2.
  - Files: `clients/godot-observer/scripts/ui/` (new panel or status extension), `session.gd`, `models.gd` parse helpers, Godot tests, fixtures as needed.

<!-- Commit checkpoint: tasks 1–1b then 2–3 -->

### Phase 2: Markers and focused playback

- [x] Task 4: Configurable timeline marker categories.
  - Deliverable: Extend `timeline.gd` (+ theme colors) with category toggles per Design Decisions. Collect marks from the loaded events window first; optional enrichment with ≤3 type pages, one refresh in flight, cancel on seek/switch. Cap drawn marks at 64. Add synthetic `branch_point` marks from current lineage `fork_tick` (manifest/run fields available after task 1) and from loaded children when Task 3 data is present. Birth category is no-op until a birth-class semantic type exists. Clicking a mark seeks. Selected-agent marks remain optional and compatible with categories. Focused unit test for collect/cap/category toggles.
  - Logging: DEBUG `marks_set` with per-category counts and `truncated=%s`; no event payloads.
  - Depends on task 1 (allowlist + cancel). Branch children enrichment soft-depends on task 3 (use lineage fields alone until children load).
  - Files: `clients/godot-observer/scripts/ui/timeline.gd`, `ui_layer.gd`, `session.gd` (marker refresh), theme/presentation helpers, tests.

- [x] Task 5: Agent-focused playback (filter, next/prev, follow).
  - Deliverable: Selecting an agent sets focus using **entity id** from `world.agents`. Show related events via log filter + `agent_id=<entity_id>` refresh (requires Task 1b). Implement next/previous focused events with the locked algorithm (loaded lines → forward filtered page → reverse probe ≤32). **Follow** tracks camera/UI only via `camera_rig.focus_on` after seeks and live updates; prove no simulation control calls. Follow does not require `subjective_debug`. Focused unit tests for neighbor algorithm and follow camera-only.
  - Logging: DEBUG `focus_agent id=%s`; INFO `follow_agent enabled=%s`; DEBUG neighbor seek ticks/sequences and `focus_probe count=%s`.
  - Depends on tasks 1, 1b.
  - Files: `session.gd`, `event_log.gd`, `camera_rig.gd`, `agent_layer.gd` / `world_view.gd`, `ui_layer.gd`, tests.

- [x] Task 6: Location-focused playback (filter, follow activity).
  - Deliverable: Select location; show events with location filter + `location_id=` query on refresh. Reuse Task 5 neighbor algorithm with location filter. Follow location centers camera on the anchor; optional snap-to-next-event remains off by default. Mutual exclusion with agent Follow as locked above. Focused unit test for filter + follow mutex.
  - Logging: DEBUG `focus_location id=%s`; INFO `follow_location enabled=%s`.
  - Depends on task 5.
  - Files: `session.gd`, `location_layer.gd` / `world_view.gd`, `event_log.gd`, `ui_layer.gd`, tests.

<!-- Commit checkpoint: tasks 4–6 -->

### Phase 3: Bookmarks and usability

- [ ] Task 7: Local researcher bookmarks.
  - Deliverable: Persist bookmarks under `user://observer_bookmarks/<safe_stem>.json` with filesystem-safe stem + original `run_id` in JSON; fields tick, optional sequence, note, `created_at_utc`. UI to add (default note empty or short prompt), list, edit note, delete, and jump (seek). Bookmarks survive run switches for that `run_id` and must not be written to any simulation API. Document Web persistence limits in code comment + docs task. Empty list empty-state. Focused unit test for sanitize stem, persist/reload, jump seek.
  - Logging: INFO `bookmark_jump tick=%s`; DEBUG add/delete with tick/sequence and `note_len` only.
  - Depends on task 1.
  - Files: new `clients/godot-observer/scripts/ui/bookmarks.gd` (or `protocol/bookmarks.gd` store + UI), `ui_layer.gd`, `session.gd`, tests (temp `user://` paths).

- [ ] Task 8: Usability chrome — shortcuts, status, inspector, descriptions.
  - Deliverable: Implement keyboard shortcuts (without breaking LineEdit focus), loading/seeking/switching indicators, connection + LIVE/REPLAY/behind-live badges, clearer protocol-mismatch and empty-state copy, richer selected-agent inspector (still read-only objective snapshot fields), and improved `_describe` strings for major env/artifact/structure events. Verify Web export constraints (no thread features, shortcuts work in browser when focus is not in a text field). Focused unit tests for describe strings and status copy; shortcut wiring covered in Task 9 where hard to unit-test headlessly.
  - Logging: DEBUG `shortcut action=%s`; status transitions already INFO/DEBUG via session; inspector DEBUG on open.
  - Depends on tasks 5–7 for follow/bookmark shortcuts.
  - Files: `main.gd` / `ui_layer.gd`, `status_bar.gd`, `inspector.gd`, `event_log.gd`, `project.godot` InputMap if used, tests.

<!-- Commit checkpoint: tasks 7–8 -->

### Phase 4: Integration tests and docs

- [ ] Task 9: Integration Godot suite for advanced navigation.
  - Deliverable: Automated Godot **integration** tests (not a second copy of every unit proof) covering end-to-end: clean switch (no merged state); nav stack return; marker category collect/cap including synthetic branch_point; agent next/prev focus including actor|target semantics via fixtures; follow does not call non-GET control routes; bookmarks persist per run_id (safe stem) and jump seeks; protocol mismatch copy/reason; URL allowlist accepts focus/branch keys. Assert key log tokens where practical. Rely on Tasks 1–8 for focused unit coverage.
  - Logging: tests assert tokens such as `run_switched`, `branch_open_`, `follow_agent`, `bookmark_jump`, `unsupported_observer_protocol`, `agent_match_mode` (Python side covered in Task 1b tests).
  - Depends on tasks 1–8.
  - Files: `clients/godot-observer/tests/*.gd`, fixtures as needed.

- [ ] Task 10: Documentation checkpoint via `/aif-docs` ownership.
  - Deliverable: Update `docs/godot-observer.md` and `docs/research-api.md` for branch navigation, `agent_id` actor|target filter semantics, marker categories + fetch budget, agent/location follow (presentation-only), local bookmarks + safe stem + Web persistence caveat, shortcuts, and status indicators. No README bloat beyond a one-line pointer if the landing page already links docs. State explicitly that bookmarks are not authoritative history.
  - Logging: n/a (docs only).
  - Depends on tasks 8–9.
  - Files: `docs/godot-observer.md`, `docs/research-api.md`.

<!-- Commit checkpoint: tasks 9–10 -->
