# Phase 4: Generational world view and lineage navigation

Plan: [index.md](index.md)  
Tasks: 9–10  
Depends on: Tasks 6–7 for Task9; Tasks8–9 for Task10

## Objective

Present demographics, caregiving, learning and lineage through optional researcher chrome while retaining the existing location graph, movement rules and V2 controls.

## Current-Code Evidence

| Path | Symbols / section | Why it matters |
|---|---|---|
| `clients/godot-observer/scripts/view/agent_token.gd` | `setup`, `_draw` | Living/dead tokens and selection ring; add badges without replacing identity. |
| `clients/godot-observer/scripts/view/agent_layer.gd` | `show_world`, `capture_positions`, `highlight` | Existing location-local token placement and focus. |
| `clients/godot-observer/scripts/view/world_view.gd` | `show_world`, `replace_sought_frame`, `_on_agent_selected`, `focus_agent` | Existing presentation positions, inspector signals and seek behavior. |
| `clients/godot-observer/scripts/protocol/event_router.gd` | `route` | Lifecycle/feed/transport event categories exist; `other_id` currently excludes feed/transport. |
| `clients/godot-observer/scripts/ui/overlay_legend.gd` | overlay registry | Evidence-class chrome and default-off controls. |
| `clients/godot-observer/scripts/presentation/evidence_class.gd` | `OVERLAY_CLASSES`, `for_overlay` | Unknown kinds default to analytical; every new objective control must be explicitly registered. |
| `clients/godot-observer/scripts/view/world_view.gd`, `scripts/ui/inspector.gd` | `focus_agent(entity_id)`, `show_agent`, `clear_agent` | Focus expects body identity; inspector is hidden without selection, so global population controls cannot live only inside it. |
| `clients/godot-observer/scripts/ui/timeline.gd` | `_collect`, `_drawn_marks`, `_gui_input` | Marker cap, tick-start versus event-prefix seek. |
| `clients/godot-observer/scripts/ui/inspector.gd` | `show_agent` | Existing selected-agent inspector. |
| `clients/godot-observer/scenes/world_view.tscn` | world layer tree | Insert presentation-only overlays; preserve optional existing teaching hook. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `clients/godot-observer/scripts/view/agent_token.gd` | modify | Optional demographic badges and stage labels. |
| `clients/godot-observer/scripts/view/agent_layer.gd` | modify | Apply sidecar badges keyed by backend entity identity. |
| `clients/godot-observer/scripts/view/generational_overlay.gd` | create | Distinct objective kinship/care and evidence-labeled mentorship links. |
| `clients/godot-observer/scripts/view/world_view.gd` | modify | Apply/clear sidecars and feed overlay existing token points. |
| `clients/godot-observer/scripts/protocol/event_router.gd` | modify | Preserve care actor/recipient endpoints for presentation. |
| `clients/godot-observer/scripts/ui/generational_panel.gd` | create | Global population/group controls plus selection-scoped lineage tabs/cards and signals. |
| `clients/godot-observer/scripts/ui/inspector.gd` | modify | Selected-agent demographic fields and selection integration with the independent panel. |
| `clients/godot-observer/scripts/ui/overlay_legend.gd` | modify | Default-off demographic/kinship/mentorship controls. |
| `clients/godot-observer/scripts/presentation/evidence_class.gd` | modify | Register objective overlay kinds and scoped mentorship variants; map closed lineage wire classes to presentation classes. |
| `clients/godot-observer/scripts/ui/timeline.gd` | modify | Backend generation marker category and boundary seeking. |
| `clients/godot-observer/scripts/main.gd` | modify | Connect panel/session/view/timeline signals and reset path. |
| `clients/godot-observer/scenes/ui/generational_panel.tscn` | create | Scrollable panel with accessible labeled controls. |
| `clients/godot-observer/scenes/ui/ui_layer.tscn` | modify | Mount the default-hidden generational panel independently of selected-agent inspector. |
| `clients/godot-observer/scenes/ui/inspector.tscn` | modify | Preserve existing inspector and add selected-agent demographic fields only. |
| `clients/godot-observer/scenes/world_view.tscn` | modify | Add generational overlay node. |
| `clients/godot-observer/tests/test_generational_view.gd` | create | Actual badge/link/selection state assertions. |
| `clients/godot-observer/tests/test_generational_navigation.gd` | create | Panel/card/navigation tests. |
| `clients/godot-observer/tests/test_timeline_markers.gd` | modify | Generation marker seeking, cap, dedup and reset. |
| `clients/godot-observer/tests/run_protocol.gd` | modify | Register new suites. |

## Task 9: Render population, lifecycle, arrival, death and care

### Intent

Make objective demographic changes visible without assigning social roles or adding physical coordinates.

### Implementation Steps

1. Mount `GenerationalPanel` as a top-level UI-layer child, not solely inside the selection-hidden inspector. A default-off Population control opens its summary/group lists without requiring an agent selection; selected-agent tabs are hidden until an agent is chosen. Header shows exact living/admitted/dead totals, backend stage rows plus truncation indicator, and cursor/OBJECTIVE label. Cohort/generation breakdowns use their own paged sections and Load more, never unbounded summary arrays. Never sum only a fetched roster/group page. A population delta may be displayed only between consecutive accepted full-boundary summaries and is labeled with both ticks; no delta on first view, partial prefixes, stale live data, source changes or arbitrary seeks.
2. Register `population`, `generation`, `cohort`, `age_stage`, `kinship`, and `caregiving` as OBJECTIVE in `EvidenceClass.OVERLAY_CLASSES`; register `mentorship_subjective` and `mentorship_analytical` separately under the existing subjective/analytical constants. Add a closed mapping from lineage wire values `objective|subjective|analytical` to existing presentation constants; reject unknown values rather than allowing the default analytical fallback to mislabel a demographic fact. Add default-off Generation/Cohort/Age-Stage controls. Badges use server labels and deterministic presentation colors while preserving identity color and selection outline. Age/stage includes text/shape, not color alone. Dead tokens retain death cross and show last recorded stage with unavailable age. Missing rows show unknown/loading, never zero/default.
3. Display new arrival from existing explicit `AGENT_CREATED`/`AGENT_ENTERED_WORLD`/`AGENT_INITIALIZED` events. Deduplicate transient entrance highlighting per target body and tick so initialization siblings do not produce three births. UI text is “arrival / admitted”; biological “birth” is not asserted. Loading an initial roster does not animate everyone as newborn.
4. Preserve existing death display. Stage refresh uses the cursor-matched sidecar, not age arithmetic. Backward seek/scrub clears transient arrival/death/care effects; replay may show static state but must not replay forward animation backward.
5. Extend the event router's `other_id` eligibility to feed/transport and ensure world-view care effects use committed actor/target endpoints. In `generational_overlay.gd`, display bounded recent care occurrences from the already loaded event window: event type, actor, recipient, tick and occurrence location. Use 100-event ring capacity, dedup by event ID, and clear on source replacement/backward seek. Feed/transport is observed action, not permanent caregiver status, affection or parenthood.
6. All arrows attach to `AgentLayer.capture_positions()` or existing location centers. Off-screen/absent/dead historical endpoints remain list entries with unresolved-position labels; do not create ghost bodies or move them into a family layout. Transport retains atomic backend placement and existing discrete regional journey rendering.
7. Add compact read-only presentation diagnostics for acceptance: safe counts/booleans emitted only after model application (`demographics_rendered`, `care_rendered`, generation marker count). They must reflect actual model/control state, not unconditional success strings.

### Required Interfaces and Contracts

`GenerationalPanel.apply_demographics`, `WorldView.apply_demographics`, and `GenerationalOverlay.apply_care_events` consume parsed backend data. No domain coordinates, physics, admission behavior, ages, kinship edges or learning claims are computed in rendering code. Existing follow camera, item rendering, Why? inspector, replay and branch controls remain usable.

### Requirement Evidence

User request — arrival/birth, aging, death, population, care, location-based model. `docs/generational-runner.md` — calendar generation, no biology, no parent assignment. Architecture — client positions presentation-only and no scripted caregiving.

### Error Handling and Logging

Unavailable population stays N/A with reason, not zero. Invalid identity binding clears that badge/link only. DEBUG rendered counts/tick/availability; no record payloads, content text, credentials or full URLs. Labels explain evidence class and last-observed state.

### Tests

Server fixture → parser → panel/world view: open Population before any selection; founders/later entrant/stage/death and same-tick entry; exact totals versus paged agents/groups; selected row beyond roster cache; stale live-event chrome; every new control's evidence-class registry; unknown wire-class rejection; off controls preserve V2 token state; transit counted once; arrival sibling dedup; feed/transport actor-recipient and non-kin care; unseen endpoints; backward seek clears effects; no location or movement change from overlays.

### Acceptance Criteria and Verification

Run pinned Godot two-pass suite. Assert actual label strings, token metadata, overlay endpoints/counts, model counters and unchanged token positions with overlays off/on. No tests pass merely because a log string was emitted.

## Task 10: Add generation timeline and selected-agent lineage navigation

### Intent

Parents, children, teachers, students and transmitted knowledge become explicit backend-evidence navigation, not a client-built genealogy system.

### Implementation Steps

1. Add Generation category to timeline using `set_generation_markers` with backend rows. Keep independent source identity and marker keys `(run_id, generation_index)`. Marker click emits `seek_tick` as a full-boundary seek; existing event marks still seek event prefixes. Merge deterministically under existing marker cap, show truncated/partial state, retain birth/death/branch categories, and clear on source replacement.
2. Add selected-agent tabs Parents, Children, Teachers, Students, Knowledge and Mentorship to the independent generational panel. Keep `selected_agent_id` distinct from token `entity_id`. Build an agent→body lookup only from registration-backed `agent_id`/`entity_id` pairs in the accepted backend frame; validate uniqueness and never assume the strings match. A body without an agent binding shows lineage unavailable. Parent/child rows use direct backend `parent_of` edges; deeper graph navigation is a separate action with visible depth.
3. Parents/children are OBJECTIVE and capture-dependent. Teachers/students and mentor/apprentice bonds display SUBJECTIVE owner or ANALYTICAL scope, confidence/status and observed boundary. Do not label a source on a knowledge `acquired_from` edge as a teacher without an explicit participant record. Preserve contradictory owner views.
4. Knowledge tab lists participant content cards with kind, opaque key, acquisition tick, hops, attempts/learning evidence, mutation and provenance. Heading: “Important transmitted knowledge — evidence-prioritized in loaded records”. Disclose ordering and partial-page coverage; attempt-only cards are a separate group and do not assert successful acquisition. Add knowledge-family graph exploration with server refs and evidence labels; do not invent content descriptions or cross-family links.
5. Clicking a parent/child/teacher/student updates logical selection to the returned backend agent ID, starts exact selected-agent demographics/lineage requests, and looks up its body in the accepted frame. Pass the **mapped entity ID** to existing `focus_agent`/highlight methods. If absent, retain the selected historical card and enabled Back control in the independent panel with “not present at this cursor”; do not create/move a body or clear the logical selection merely because the ordinary inspector hides. Offer explicit seek only to a backend-provided acquisition/marker boundary; founders/dead/archived agents remain navigable. Test deliberately different agent and body IDs in every navigation direction.
6. Link overlays are on demand and default off. Draw only direct server parent edges and explicit mentorship bonds/participant arrows from current selected scope; use distinct line style/evidence legend for objective versus subjective/analytical. No global family web, pedigree depth arithmetic, owner merges or installation of a social role.
7. Add bounded navigation stack of 20 `(run, agent, scope, owner, captured boundary)` entries and Back control. Clear stack/private cards/links on run/branch switch, selection clear, debug revocation and source reset; an ordinary selected-agent change invalidates in-flight requests and current graph but retains legitimate Back history within the same run.
8. Display separate states for loading, capture disabled, debug restricted, exact snapshot unavailable, partial, complete-empty, scan-limited, truncated and error. Offer explicit Load more and older-capture chooser; never silently fetch newer subjective evidence during historical viewing.

### Required Interfaces and Contracts

Generation markers are successful-admission markers, not kinship events. Native IDs/ref keys/cursors stay opaque. Cards navigate only backend-projected participants and graph refs; no name matching, generation-to-parent inference, speech-to-learning inference or hidden all-owner query.

### Requirement Evidence

User request — generation markers and all five navigation categories. `docs/lineage-explorer.md` — capture, qualified identities, coverage and cursor rules. `docs/generational-runner.md` — generation/cohort/kinship distinction.

### Error Handling and Logging

Late/failed lineage responses never replace the current inspector's data. Restricted sections clear their content immediately. INFO panel availability and source reset; DEBUG counts/boundaries/stale reason only. No credentials, cursors or participant content in logs.

### Tests

Marker boundary seek and founder tick0; missing generation/denied slot; toggles/cap/reset. Parent→child→Back and teacher→student navigation with different agent/body IDs; exact selected-row request outside loaded pages; dead parent/absent-at-cursor student retains logical panel selection and Back; owner claims; attempt-only teaching; content graph link; capture missing/unauthorized debug; genuinely partial prefix versus complete last-event frame; evidence registry/scope switching; source/credential races. Assert correct headers/requests and visible UI state, not screenshots alone.

### Acceptance Criteria and Verification

`"${GODOT_BIN}" --headless --editor --path clients/godot-observer --quit`

`"${GODOT_BIN}" --headless --path clients/godot-observer --script res://tests/run_protocol.gd`

Expected: all existing and new suites pass on Godot 4.7.2-stable; generation markers reach committed entrants; every link/card can be traced to a backend response.

## Phase Risks and Mitigations

- Family rendering can imply world-space physics: attach links only to presentation positions and keep location placement unchanged.
- A parent can be mistaken for a caregiver or teacher: separate event/evidence layers and explicit labels.
- Existing generic teaching overlay hooks can conflict: keep their existing behavior; the generational layer renders only scoped native participant evidence and clears independently.

## Phase Completion Checklist

- Population and lineage controls work without replacing V2 controls.
- Evidence classes, cursor, availability and caps are visible.
- Update only `index.md` progress after passing tests.
