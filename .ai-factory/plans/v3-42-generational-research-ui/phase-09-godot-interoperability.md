# Phase 9: Bidirectional Godot focus links

Plan: [index.md](index.md)  
Tasks: 21–22  
Depends on: Tasks 1, 2, 7, 9, 12, 14, 16, 20

## Objective
Make run/tick/agent/location/institution/narrative/technology links work in both applications, including tick-only seek and unsupported/unavailable focus feedback.

## Current-Code Evidence
| Path | Symbols | Why it matters |
|---|---|---|
| `clients/godot-observer/scripts/net/origin.gd` | `web_debugger_state` | Existing parser lacks new entity selectors and strict integer parity |
| `clients/godot-observer/scripts/net/session.gd` | `apply_web_query`, `_apply_pending_deeplink`, `seek_tick`, `seek_event`, `set_location_focus` | Pending handler currently seeks only tick+sequence; agent is parsed but not applied there |
| `clients/godot-observer/scripts/protocol/research_ui_link.gd` | `ResearchUiLink` | Existing outbound helpers, positional compatibility matters |
| `clients/godot-observer/scripts/main.gd` | lineage/agent selection handlers | Reuse established inspector and navigation affordances |
| `clients/research-ui/src/embed/GodotEmbed.svelte` | iframe/new-tab fallback | Optional embed, no authority-sharing channel |

## Files to Change
Modify the five files above, `clients/godot-observer/scripts/ui/ui_layer.gd`, `clients/godot-observer/scenes/ui/ui_layer.tscn`, `clients/godot-observer/scripts/protocol/urls.gd`, `clients/godot-observer/tests/test_web_run_id.gd`, `test_research_ui_link.gd`, `test_generational_navigation.gd`, `tests/run_protocol.gd`, `clients/research-ui/src/deeplink.ts`, `src/views/RunOverview.svelte`, `src/embed/GodotEmbed.svelte`. Introduce `clients/godot-observer/scripts/net/research_focus.gd`, `scripts/ui/research_focus_panel.gd`, `tests/test_research_focus.gd`; new TS Godot-link/embed tests. Use the phase1 corpus from repository path in tests only; do not add filesystem access to the exported client.

## Task 21: Extend Godot parsing, pending seek and focus resolution
Depends explicitly on Task7's verified endpoint/identity mapping, in addition to Tasks1,9,12,14,16,20.

### Intent
A valid link must actually seek and select, not merely retain query strings.
### Implementation Steps
1. Extend ObserverOrigin with phase1 canonical selectors, matching case-insensitive secret-key rejection and strict canonical safe nonnegative integers. Reject ambiguous focus and incomplete subjective qualifiers. Preserve existing layout/civilization/debugger options. Do not parse credentials or allow origin URLs in focus fields.
2. In session pending application, use `seek_event` for tick+sequence, `seek_tick` for tick alone, and current finalized frame when no cursor. Queue focus until the requested run bootstrap and matching seek complete. Bind pending focus to HTTP/run/seek/credential epoch so later navigation cancels it.
3. Introduce `ResearchFocusController` in `research_focus.gd`, independent of `LineageSource`'s hard-coded genealogy/participants/knowledge panels. Interface: `set_request_sink(Callable)`, `set_context(run_id,epoch,credential_generation)`, `on_frame(frame)`, `resolve_selection(selection)`, `handle_response(meta,body,reason,status)`, `invalidate_private(reason)`, `clear()`, `changed` signal and bounded public `state`. Agent/location focus reuses existing session selection after frame validation. For lineage entities use Task7's verified sequence: restricted family discovery under debug, optional publication→snapshot boundary/digest discovery, exact root-key or native-filter lookup, qualified identity match, bounded traversal with returned snapshot checks. Analytical query scope never includes native `identity_owner`. No unsupported publication-ID query key is sent to lineage.
4. For civilization-source institution/technology focus, use existing strict civilization protocol parser and catalogue/overlay endpoints with the source's own `publication_id`, evidence class and subjective-only scope owner. Concepts/office/episodes match exact row/entity/native owner/kind. Technology content keys are not native entry IDs; preserve source refs and row ID, page the technology overlay within a fixed row budget rather than sending unsupported `knowledge_id`/`entity_id` searches. Missing exact row is explicitly unresolved, never mapped to a similar lineage node. Do not infer a concept's world location or add a registry.
5. Wire the controller into ObserverSession construction with `set_request_sink(Callable(self,"_request_path"))`; every request meta has `source="research_focus"`, expected JSON root, run/seek/focus epoch and credential generation. Add source dispatch in the shared response handler adjacent to existing generational/lineage/civilization branches, plus the local request-build failure branch. Forward only current matching-frame completion to `on_frame`/pending focus application. Clear/invalidate on run switch, seek replacement, disconnect, credential apply/forget and panel close; stale replies cannot reopen it. Existing private-lineage state remains independent. Add `entity_id` and `cursor` to `ObserverUrls`' GET allowlist only where required by existing civilization focus/filter paging; never add credential/URL passthrough.
6. Mount a real ResearchFocusPanel node in `scenes/ui/ui_layer.tscn`, attach `research_focus_panel.gd`, and expose `set_research_focus(state)` plus focus-open/back/share signals through `scripts/ui/ui_layer.gd`. In `main.gd`, connect the controller's changed signal to this setter and UI navigation/share actions back to session/ResearchUiLink. Render source, qualified ID/class/identity owner, requested/captured boundary, coverage, root status, bounded ancestor/descendant metadata table or civilization row metadata, and Open Research. No Godot analytical calculator/chart implementation. Unsupported kind, capture absence or forbidden scope preserves shareable selection and shows a visible reason.
7. At event-prefix time, agent/location focus may resolve, but captured lineage/civilization research focus shows `finalized_boundary_required` and offers full-boundary navigation. Never silently seek later. Tick-only seek must complete before any focus-dependent reads.
### Required Interfaces and Contracts
Protocol stays `observer-protocol-v1`; only credential-free presentation URL contract expands. No backend mutations/automatic capture. A missing entity is visibly unresolved, never label-matched. Scope owner and identity owner are separate; source/family/row/publication fields survive round trips. Controller caps default depth2/nodes200/edges500, returned server smaller caps win, and initial root/snapshot lookup scans at most500 rows per explicit load action. Its request identity includes focus epoch even when run/tick stay the same.
### Requirement Evidence
User seven focus dimensions; actual existing pending-seek defect; lineage signed snapshot and evidence auth rules.
### Error Handling and Logging
Reason codes, focus kind, seek outcome and counts only; no full URLs/credential/entity payload. A cancelled seek cannot reopen a stale inspector. Missing debug remains forbidden, not fallback to objective institution.
### Tests
Shared fixtures, tick-only0/nonzero, tick+sequence, bootstrap-before-focus, actual agent/location selection, institution/narrative/technology exact query and metadata panel, absent capture, wrong owner, prefix, credential casing and stale epochs. Add source-dispatch tests delivering both success and locally rejected GET responses through ObserverSession, not directly to the controller; assert mounted scene node text and share action via ui_layer/main. Cover subjective civilization concept, office-succession lineage, analytical episode with identity owner/no scope owner, technology repeated content key, explicit old publication, pagination and swapped root/publication responses. Existing genealogy/teaching/knowledge panels must remain unchanged.
### Acceptance Criteria
All seven link dimensions have observable resolution or an honest unavailable/forbidden result at the requested run/time; no merely parsed-but-unused selector.
### Verification
`"${GODOT_BIN}" --headless --editor --path clients/godot-observer --quit` then `"${GODOT_BIN}" --headless --path clients/godot-observer --script res://tests/run_protocol.gd`, using pinned Godot4.7.2.

## Task 22: Complete outbound links and Research UI/Godot round trips
### Intent
Selection must survive copy/open/back across both applications without leaking credentials or silently dropping entity qualification.
### Implementation Steps
1. Extend ResearchUiLink helpers with a trailing optional options dictionary to preserve all existing positional calls. Serialize phase1 keys and validate VIEWS from shared fixtures. Preserve source, lineage family/key or civilization row ID, native kind, evidence, separate identity/scope owners, source-specific publication and complete cohort tuple. Existing old links keep format/meaning. A subjective institution concept round-trips as civilization focus, not invalid subjective institution-lineage focus.
2. Build UI→Godot URLs from canonical focus selection. Generation-only UI state must resolve to actual marker tick before opening Godot; an unresolved generation disables Open with explanation rather than dropping time. Matrix IDs are never substituted for run IDs.
3. Godot focus inspector adds Open Research for its selected root; agent/location interactions and narrative/technology/institution metadata all expose canonical outbound options. Route to relevant UI view without dropping tick or identity; browser uses `noopener,noreferrer`, desktop same-origin resolved URL only.
4. Keep optional iframe isolated. Add an accessible explicit new-tab fallback and clear loading/error instructions; do not add a credential-bearing postMessage channel or claim iframe load proves successful backend bootstrap. URLs never contain stored credentials.
### Required Interfaces and Contracts
Round trip preserves run/tick/focus, source, qualified identity/scope owners, class/native kind and composite cohort selection. Lineage and civilization publications remain in their distinct named fields and are never substituted for each other. Credentials are entered independently in each application. Retain event debugger links and existing browser security flags.
### Requirement Evidence
User Godot deep links; phase1 canonical link corpus; existing ResearchUiLink and GodotEmbed behavior.
### Error Handling and Logging
Unsupported link selection offers a visible reason, never silently opens overview. Logs view/focus kind/outcome only. Popup-blocked/new-tab actions provide a normal anchor fallback.
### Tests
TS builder→Godot fixture→outbound builder→Python/TS parser parity for all seven dimensions; escaped IDs, subjective concept civilization focus, office succession, analytical institution identity with null scope owner, separate publication namespaces, reused cohort IDs/composite identity, generation resolution, legacy debugger URLs, missing run, origin injection and secret-free iframe/new-tab URLs. Assert actual controller/scene resolution, not parser equality alone; mounted embed fallback test.
### Acceptance Criteria
Both applications can share every requested focus type and retain exact time/identity safely.
### Verification
`pnpm --dir clients/research-ui test src/deeplink.test.ts src/embed/GodotEmbed.test.ts`; Godot suite above; `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_research_ui_state.py -q`.

## Phase Risks and Mitigations
Session seek is asynchronous: bind focus to epochs, not a single global pending dictionary with no ownership. Godot additions stay a small research-focus inspector, not a duplicate Research UI.

## Phase Completion Checklist
Cross-client fixture parity and real seek/focus tests pass; record index progress only.
