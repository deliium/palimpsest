# Implementation Plan: Godot Observer Timeline and Replay

Branch: main
Created: 2026-09-28
Improved: 2026-09-28 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete milestone; this plan adds read-only timeline and replay controls and does not claim `advanced_social_inference`, `multi_hop_testimony_tracking`, or any new capability flag.

## Compatibility contract

This plan extends the read-only observer query and the Godot presentation client. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants stay intact. `WorldEngine` remains the only objective mutation authority. Playback controls call existing observer GET routes and the observer WebSocket. They never call simulation control, admission, or any other mutating route.
2. No new capability flag. No `V2CapabilityFlags` slot, no `runner-config` bump, and no Alembic revision.
3. V1 regression gate stays green under flags-off and tracing-off. The client is not an experiment arm and must not be appended to `tests/unit/test_v1_regression_gate.py`.
4. No schema bump of authoritative history. Stay on `observer-protocol-v1` and `observer-layout-v1`. The new query is optional. `GET .../state` and `GET .../state?tick=` keep their current meaning.
5. No scripted emergence. Timeline markers, log phrases, and colors do not add graph edges, roles, or milestone scripts.
6. No LLM involvement.
7. Experiments stay reproducible. Play, pause, speed, seek, and filters must not change seeds, event ids, or `exact_trajectory_hash`. Playback speed is never sent to the server.
8. Optional cognition tracing stays outside the client. Do not request cognition-trace rows, memories, beliefs, goals, emotions, or utterance text.

## Goal

A researcher watching a run can move through committed history the way an event debugger does. The user is an observer only. No control changes historical simulation results.

```text
Play / Pause / step / jump
  -> client playback cursor (run_id, tick, sequence, LIVE|REPLAY, speed)
  -> GET observer/state and GET observer/events
  -> nearest snapshot + forward event fold
  -> ObserverFrame replaces the picture
```

Going backward never applies an inverse mutation on the client or the server. Previous Event and Previous Tick request a reconstructed frame, then the view renders that frame. Correct state matters more than a reverse animation.

## Design Decisions (locked)

- **Existing tick query stays.** `GET /v1/simulations/{run_id}/observer/state?tick=T` still means the fold of events with `event.tick < T`, and `world.tick == T`. Omitting `tick` is still the durable head and `cursor.mode == "live"`. `src/simulation/replay.py` `ReplayRequest` stays tick-scoped. Do not add a public continuation mode.
- **Event cursor is an extra query.** `GET .../observer/state?tick={event_tick}&through_sequence={sequence}` folds every committed event with `(event.tick, event.sequence) <= (event_tick, sequence)`. Replay to the start of that tick with the existing snapshot path. Events of that tick are loaded from the journal. They are not already in the restored engine, because `scene_at_tick` folds only `event.tick < T`. Apply the prefix with `project_event_prefix` in `world._replay`. Do not call `project_events` on a prefix: a prefix that has not mutated, while a later event in the same tick has, raises `REVISION_MISMATCH`. `through_sequence` without `tick` is `incomplete_event_cursor`. A pair past the durable head is `cursor_ahead_of_high_water`. A pair that is not a committed event is `observer_event_not_found`. When the prefix is the whole tick, the frame matches `GET .../state?tick={event_tick + 1}`, including `world.tick`.
- **Revision and clock on a partial tick.** Apply event effects in sequence order. Assign the tick's resulting revision, and advance the clock the way `restore_from_snapshot` does for `committed_through_tick + 1`, only when the prefix includes the last event of that tick. A shorter prefix keeps the start-of-tick clock (`world.tick` stays at that tick) and still shows the occupancy, items, resources, weather, and life status produced by those events. Drop the restored engine before returning. Do not write a snapshot. The `observer` package does not import `world._replay`.
- **No protocol bump.** `ObserverFrame` already carries `cursor.sequence`, `cursor.after_tick`, and `cursor.after_sequence`. After an event seek, those after-fields are the last folded event. `frame.events` remains folded history: the client does not tween it and does not append it to the log.
- **Client playback cursor.** A GDScript model, not a new wire type. The viewed tick is the event's tick (`cursor.after_tick`), and the viewed sequence is `cursor.after_sequence`. `frame.world.tick` and `frame.cursor.tick` stay the engine high water: during a partial tick they equal the event tick, and after a finished tick they are one ahead. The timeline's current tick uses the viewed event pair. Sending that pair as a socket resume when `after_tick >= world.tick` closes with `4409`, so replay does not use it as a resume cursor.
  - `run_id`
  - viewed `tick` and `sequence` (`sequence` null only before the first event)
  - `mode` = `LIVE` or `REPLAY`
  - `speed` = one of `0.25`, `0.5`, `1`, `2`, `4`, `8`, `16`
  - `paused` is orthogonal to mode
  - `live_tick` is the high water from `GET .../observer/run` (`tick`)
  - `behind_live` is true when paused live traffic was dropped or the viewed event is behind `latest_tick` / `latest_sequence`
- **Speed stays local.** At 1x, motion stays about 0.6 seconds and speech about 2 seconds. Slower speeds lengthen those durations. Below speed 8, each step is one event and one state GET. At speed `>= 8`, advance one whole tick per state GET (the last event of that tick) and skip tweens. Also skip when more than three motions are pending. 16x uses that same whole-tick step. Rewind does not play a reverse tween. Clear in-flight tweens before applying a sought frame.
- **Live path while unpaused.** Keep today's reducer for `kind=event` while `mode=LIVE` and `paused` is false. A `tick` envelope still refreshes state. The simulation is never paused by the client.
- **Pause during live simulation.** The run continues. The socket stays up. New live events go into a buffer of at most 256 events and are not applied and not logged until the observer resumes. If another event would exceed 256, discard the buffer, set `behind_live`, and do not apply a stale prefix. The status bar shows `behind live`. Play after a discard reloads with `GET .../events` from the last applied `(after_tick, after_sequence)` and then `GET .../state`. Return to Live ignores the buffer, `GET`s `.../state` with no tick, `GET`s `.../run` for the live tick, clears tweens, sets `mode=LIVE`, and resumes the socket from that frame's cursor.
- **Step-by-step.** Next Event and Previous Event move one committed event even when several events share a tick. The stable key is `(tick, sequence)`. Sequences inside a tick are contiguous from 0, so the previous event at `sequence > 0` is `(tick, sequence - 1)`. Sequence 0 uses `GET .../ticks` for the previous tick's `last_sequence`. Next Tick lands on the last event of the next tick that has events. Previous Tick lands on the last event of the previous tick that has events. Jump to Tick uses `state?tick=` (the start of that tick) and focuses the first event of that tick in the log when the page contains it. Jump to Event uses `tick` plus `through_sequence`. At the first event, Previous Event does not wrap. At the latest known event, Next Event does not invent an event. Do not page the journal from tick 0 to find a neighbor.
- **Seek application.** Each GET carries its own request id. A response older than the latest seek is ignored. `Session` must not store the in-flight kind only by path: `http_client.gd` already queues one GET, and a second state request overwrites that kind before the first returns. Entering `REPLAY` closes the socket with the existing client-stop path so live envelopes cannot reach the reducer. After every seek: clear tweens, `show_world` from the returned `ObserverFrame`, restore location occupancy, items, resources, and weather from that frame, then highlight the selected `entity_id` again when that agent is still present, including `life_status=dead`, and refresh the inspector from the new record. If the id is absent, clear the selection and the inspector.
- **Event log.** Scrollable. On seek, replace the log with one bounded events page around that cursor (the existing page size, capped near 200 lines) and focus that row. Each line includes tick, sequence, protocol type, actor, target, and a short description. The subject is the affected body: `target_id` for `AGENT_DIED`, `NEEDS_APPLIED`, and `EXPOSURE_APPLIED` (`actor_id` may be null); `actor_id` for the other semantic types. Labels prefer `agent_id`, then the raw id. Location names prefer `display_name`, then `name`. Examples, using ids the frame actually contains: `Alice moved Village -> Forest`, `Bob searched Abandoned House`, `Alice attacked Bob`. There is no `RESOURCE_FOUND` type; a search stays `AGENT_SEARCHED`. Do not print utterance text. Clicking a line seeks that event. Filters are client-side on the loaded lines: agent (actor, target, or label), event type (exact semantic type), and location (origin, destination, or location name). No counts, charts, analysis routes, or a full-journal scan.
- **Timeline.** One compact bar: viewed event tick, live tick from `GET .../run`, `AGENT_DIED` marks from the bounded log window, and selected-agent marks from that same window. Selected-agent marks stay off until toggled. Clicking a mark seeks that event. Do not page the whole run to paint marks. Do not add a plotting library.
- **Reconnect.** An existing socket loss while `mode=LIVE` and not paused still gap-fills and refreshes state. `REPLAY` keeps the socket closed and polls `GET .../observer/run` for `live_tick`, `latest_tick`, and `latest_sequence` without applying that body as `world`. A gap page during pause or replay does not move the viewed world. After Return to Live, resume from the head cursor and open the socket. The client still never sends a WebSocket payload.
- **Logging.** GDScript stays `[observer.<area>] message key=value` with `palimpsest/log_level`. Python route logs stay on `infrastructure.logging.get_logger`. DEBUG may include run id, tick, sequence, event id, semantic type, buffer size, and reason codes. INFO is mode changes and seek completion. No tokens, seeds, coordinates at INFO, utterance text, or relationship scores.

## Non-Goals

- Pausing, stepping, or reseeding the simulation from the client
- Inverse events (`AGENT_UNMOVED`, `AGENT_UNDIED`, and every other `UN` type)
- A protocol, event-schema, runner-config, or Alembic bump
- Relationship, memory, belief, goal, emotion, or utterance inspectors
- Server-side playback speed or a playback analytics dashboard
- Changing `ReplayRequest` into a mid-tick continuation of a durable run

## Commit Plan

- **Commit 1** (after tasks 1–2): `feat(observer): reconstruct a frame through an event cursor`
- **Commit 2** (after tasks 3–5): `feat(godot): add replay transport controls`
- **Commit 3** (after tasks 6–8): `feat(godot): add the event log and timeline`
- **Commit 4** (after tasks 9–10): `test(godot): cover replay navigation and document the controls`

Each checkpoint is a git commit on `main` created when those tasks are done. Do not squash them into one commit at the end. `git.create_branches` is false, so implementation stays on the current branch.

## Tasks

### Phase 1: Event-Cursor Reconstruction

- [x] Task 1: Fold history through one event without retaining an engine.
  - Deliverable: Add `project_event_prefix` to `src/world/_replay.py`. It applies committed effects in sequence order and assigns the tick's resulting revision only when the prefix includes that tick's last event. A test in `tests/unit/test_event_projection.py` covers a non-mutating prefix followed by a later mutation in the same tick: the prefix call succeeds, the revision stays at the start-of-tick value, and the full prefix matches `project_events` of the whole tick. Do not call `project_events` on a prefix. `scene_through_event` in `src/simulation/replay.py` replays to the start of `tick` with the existing snapshot path, loads that tick's events from the journal, applies the prefix, copies facts, and deletes the restored engine. It does not call `open_durable` or write a snapshot. When the prefix is the whole tick, the frame matches `scene_at_tick` of `tick + 1`, including `world.tick`. `ReplayRequest` gains no field. `src/observer` does not import `world._replay`.
  - Logging: `[simulation.replay] observer_event_fold run_id=%s tick=%s through_sequence=%s event_count=%s snapshot_next_tick=%s` at DEBUG. ERROR uses the existing replay reason code when the snapshot or range cannot be folded. No seeds and no event payloads. The prefix test asserts revision and effect results. The fold log tokens are asserted with the replay test in task 2.
  - Files: `src/world/_replay.py`, `src/simulation/replay.py`, `tests/unit/test_event_projection.py`.

- [x] Task 2: Serve the event cursor on the existing state route.
  - Deliverable: `GET .../observer/state` accepts optional `through_sequence` (`ge=0`). The behaviors in Design Decisions are enforced in `src/api/observer_service.py` and `src/api/routes/observer.py`. `cursor.mode` is `replay` whenever `tick` or `through_sequence` is present. Tests in `tests/unit/test_observer_replay.py` and `tests/unit/test_observer_api.py` cover: forward step from sequence 0 to sequence 1 inside one tick; a backward pair of reads that reconstruct sequence 0 again without an inverse event; next and previous tick boundaries; a jump whose snapshot `next_tick` is well before the target; first event and last event; a dead agent present after the death event and absent from the earlier sequence; tick-only reads unchanged; engine not retained. Architecture imports stay as they are.
  - Logging: route DEBUG `route_observer_state_cursor run_id=%s tick=%s through_sequence=%s`. Existing INFO `route_observer_state` stays. `observer_replay_loaded` includes `through_sequence`. The replay test asserts the tokens `observer_event_fold`, `tick=`, and `through_sequence=`.
  - Depends on task 1.
  - Files: `src/api/observer_service.py`, `src/api/routes/observer.py`, `tests/unit/test_observer_replay.py`, `tests/unit/test_observer_api.py`.

<!-- Commit checkpoint: tasks 1–2 -->

### Phase 2: Playback Cursor and Controls

- [x] Task 3: Add a client playback cursor and speed table.
  - Deliverable: `clients/godot-observer/scripts/protocol/transport.gd` is a `RefCounted` model with the cursor fields from Design Decisions. The viewed tick and sequence are the event pair, not `frame.world.tick`. Pure functions choose the next event, the previous event (`sequence - 1` when `sequence > 0`, otherwise the previous tick's `last_sequence`), the next and previous tick, and the live head. Below speed 8 the step target is one event. At speed `>= 8` the step target is the last event of the next tick. Speed policy in `scripts/protocol/playback.gd` accepts `0.25` and `0.5` (longer tweens) and treats `8` and `16` as skip. `tests/test_playback.gd` and a new `tests/test_transport.gd` are registered in `tests/run_protocol.gd`.
  - Logging: `[observer.transport] cursor_set mode=%s tick=%s sequence=%s speed=%s paused=%s` at DEBUG. `[observer.playback] motion_skipped speed=%s pending=%s` stays at DEBUG.
  - Depends on task 2.
  - Files: `clients/godot-observer/scripts/protocol/transport.gd`, `clients/godot-observer/scripts/protocol/playback.gd`, `clients/godot-observer/tests/test_transport.gd`, `clients/godot-observer/tests/test_playback.gd`, `clients/godot-observer/tests/run_protocol.gd`.

- [x] Task 4: Seek by replacing the frame, including backward steps.
  - Deliverable: `scripts/net/session.gd` gains read-only requests for `state?tick=`, `state?tick=&through_sequence=`, `events`, `ticks`, and `run`. Each GET has its own request id. Ignore a response older than the latest seek. Do not key the in-flight kind only by path. URLs stay GET and still omit a negative resume pair. Entering `REPLAY` closes the socket with the existing client-stop path. A seek response goes through `world_view` as a full replace: clear motions on the agent and effects layers, then `show_world`. Do not call the local reducer to undo a move, death, item, resource, or weather change. After the rebuild, highlight the selected `entity_id` again when that agent remains, including `dead`, and refresh the inspector from the new record. If the id is absent, clear the selection and the inspector. `frame.events` is not animated and is not copied into the log. The viewed tick stored on the transport cursor is `cursor.after_tick`. The applied event, if the caller passes it, may tween only in the forward direction and only when the speed policy does not skip.
  - Logging: `[observer.session] seek_started tick=%s sequence=%s` at DEBUG. `[observer.session] seek_applied mode=%s tick=%s sequence=%s` at INFO. `[observer.view] motions_cleared` at DEBUG. `[observer.session] seek_failed reason_code=%s` at ERROR. `[observer.session] seek_ignored reason_code=stale_response` at DEBUG.
  - Depends on task 3.
  - Files: `clients/godot-observer/scripts/net/session.gd`, `clients/godot-observer/scripts/protocol/urls.gd`, `clients/godot-observer/scripts/view/world_view.gd`, `clients/godot-observer/scripts/view/agent_layer.gd`, `clients/godot-observer/scripts/view/effects_layer.gd`.

- [x] Task 5: Add the transport controls.
  - Deliverable: the controls row in `scenes/ui/ui_layer.tscn` gains Play, Pause, Previous Event, Next Event, Previous Tick, Next Tick, Jump to Tick, Jump to Event, and Return to Live, plus speed buttons `0.25x`, `0.5x`, `1x`, `2x`, `4x`, `8x`, and `16x`. Existing zoom, reset, focus, and Play fixture stay. Buttons emit signals only. They do not build HTTP URLs in the scene script. Changing speed does not seek and does not write a project setting to the server. `scripts/main.gd` wires the signals to the session and the transport model.
  - Logging: `[observer.ui] control_pressed action=%s` at DEBUG. `[observer.ui] speed_selected speed=%s` at DEBUG.
  - Depends on task 4.
  - Files: `clients/godot-observer/scenes/ui/ui_layer.tscn`, `clients/godot-observer/scripts/ui/ui_layer.gd`, `clients/godot-observer/scripts/main.gd`.

<!-- Commit checkpoint: tasks 3–5 -->

### Phase 3: Log, Live Pause, and Timeline

- [x] Task 6: Show a textual event log that can seek.
  - Deliverable: On seek, `Session` loads one events page around that cursor and `scripts/ui/event_log.gd` replaces its lines with that page, capped near 200 lines, then focuses the sought row. The line is `{tick}:{sequence} {type} {actor} {target} {description}`. The subject is `target_id` for `AGENT_DIED`, `NEEDS_APPLIED`, and `EXPOSURE_APPLIED`, and `actor_id` otherwise. Labels prefer `agent_id` from the current frame, then the raw id. Location names prefer `display_name`, then `name`. The description is a short phrase for the closed semantic types (moved, searched, took, dropped, gave, ate, drank, slept, talked, asked, told, helped, attacked, fled, waited, weather, resource regenerated, needs, exposure, died). Unknown types still render and do not raise. Clicking a row emits `seek_requested(tick, sequence)`, wired to the task 4 seek path. Three filters (agent, event type, location) hide non-matching rows and do not request a new route. Empty filters show every loaded line. Live append still sorts by `(tick, sequence)`. Do not page from tick 0 to fill the log.
  - Logging: `[observer.log_view] line_appended tick=%s sequence=%s type=%s` stays at DEBUG. `[observer.log_view] seek_clicked tick=%s sequence=%s` at DEBUG. `[observer.log_view] filter_set agent=%s type=%s location=%s shown=%s` at DEBUG. `[observer.log_view] window_replaced count=%s tick=%s sequence=%s` at DEBUG. No utterance text.
  - Depends on tasks 4 and 5.
  - Files: `clients/godot-observer/scripts/ui/event_log.gd`, `clients/godot-observer/scenes/ui/event_log.tscn`, `clients/godot-observer/scripts/ui/ui_layer.gd`.

- [x] Task 7: Pause on the live run, show when the view falls behind, and return to live.
  - Deliverable: while `mode=LIVE` and `paused` is true, `Session` buffers up to 256 `kind=event` envelopes and does not call `play_event` or the reducer. Event 257 discards the buffer and sets `behind_live`. The status bar shows `behind live` until Return to Live or a successful catch-up. Play applies a surviving buffer in order, or reloads through the events keyset and `GET .../state` after a discard, then continues. `REPLAY` keeps the socket closed for the whole replay and polls `GET .../observer/run`. That poll updates `live_tick`, `latest_tick`, and `latest_sequence` and does not replace `world`. `behind live` is also shown when the viewed event is behind that head. A gap or envelope during replay or pause does not move the viewed world. Return to Live performs the unscoped state GET, updates `live_tick` from the run response, clears the buffer and tweens, sets `mode=LIVE` and `paused=false`, and opens the socket at the head cursor. A socket close while live and unpaused keeps today's gap-fill. The status text is visible without reading the log.
  - Logging: `[observer.session] live_paused tick=%s sequence=%s` at INFO. `[observer.session] live_buffer_discarded count=%s reason_code=buffer_limit` at WARN. `[observer.session] return_to_live tick=%s sequence=%s` at INFO. `[observer.session] live_head_polled tick=%s` at DEBUG. `[observer.stream] gap_ignored reason_code=replay_cursor` at DEBUG.
  - Depends on tasks 4 and 5.
  - Files: `clients/godot-observer/scripts/net/session.gd`, `clients/godot-observer/scripts/ui/status_bar.gd`, `clients/godot-observer/scripts/protocol/transport.gd`.

- [x] Task 8: Draw a compact timeline.
  - Deliverable: a new `scripts/ui/timeline.gd` and `scenes/ui/timeline.tscn`, instanced from `ui_layer.tscn`. It shows the viewed event tick and the live tick. `AGENT_DIED` marks come only from the bounded log window. Selected-agent marks use that same window and stay off until toggled. Clicking a mark emits the same seek signal as the log. The control does not plot series, heatmaps, or metrics, and it does not page the journal to discover marks. It does not call the relationship route.
  - Logging: `[observer.timeline] marks_set death_count=%s selected_count=%s viewed_tick=%s live_tick=%s` at DEBUG. `[observer.timeline] mark_clicked tick=%s sequence=%s` at DEBUG.
  - Depends on tasks 6 and 7.
  - Files: `clients/godot-observer/scripts/ui/timeline.gd`, `clients/godot-observer/scenes/ui/timeline.tscn`, `clients/godot-observer/scenes/ui/ui_layer.tscn`, `clients/godot-observer/scripts/ui/ui_layer.gd`.

<!-- Commit checkpoint: tasks 6–8 -->

### Phase 4: Navigation Tests and Docs

- [x] Task 9: Cover the playback cases in the headless runner.
  - Deliverable: GDScript tests, wired into `tests/run_protocol.gd`, exercise the pure pieces and session doubles (no network) for the cases below. Python tests from tasks 1 and 2 already own the prefix revision, snapshot jumps, and the intra-tick fold. Do not start Godot from default pytest.
    - Below speed 8, forward playback advances one event and requests `through_sequence`. At speed `>= 8`, the step target is the last event of the next tick.
    - Backward event navigation requests the previous pair and replaces state from the frame.
    - Tick navigation lands on the last event of the neighboring tick.
    - Pause while a fake socket emits events leaves the viewed world unchanged and sets `behind live` after 256 extra events.
    - Return to Live clears `behind_live`, requests unscoped state, and sets `mode=LIVE`.
    - A socket-loss signal during `REPLAY` does not apply the gap, because the socket stays closed. The same signal during unpaused `LIVE` still requests the gap.
    - Speed `0.25` lengthens the tween, speed `16` sets `skip`.
    - A sought frame that drops an entity clears selection; a sought frame that still contains that entity as `dead` keeps the selection and the dead marker.
    - Seeking the first index and the last index does not wrap.
    - `tests/test_event_log.gd` covers an affected-body line (`AGENT_DIED` uses `target_id`), the three filters, and a click that emits `(tick, sequence)`.
  - Logging: the pause test asserts the WARN token `live_buffer_discarded` and `reason_code=buffer_limit`. The log test asserts `seek_clicked` and `filter_set`. No new production logger.
  - Depends on tasks 3–8.
  - Files: `clients/godot-observer/tests/test_transport.gd`, `clients/godot-observer/tests/test_session_cursor.gd`, `clients/godot-observer/tests/test_playback.gd`, `clients/godot-observer/tests/test_event_log.gd`, `clients/godot-observer/tests/run_protocol.gd`.

- [x] Task 10: Document the controls and the event query.
  - Deliverable: `docs/observer.md` documents `through_sequence`, the unchanged tick-only query, and that a partial tick is a read-only fold. `docs/godot-observer.md` lists the controls, the speed steps, the log columns, the three filters, the timeline marks, pause versus the continuing run, `behind live`, and Return to Live. Both pages state that these controls do not change the run. Route `/aif-docs` for the docs checkpoint; do not mount the client from FastAPI.
  - Logging: no production logger. Doc examples use the `[observer.session] seek_applied` shape and do not include a token.
  - Depends on tasks 2 and 5–8.
  - Files: `docs/observer.md`, `docs/godot-observer.md`.

<!-- Commit checkpoint: tasks 9–10 -->
