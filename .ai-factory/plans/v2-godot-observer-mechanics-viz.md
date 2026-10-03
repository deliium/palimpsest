# Implementation Plan: Expand Godot Observer for V2 Mechanics Visualization

Branch: main
Created: 2026-10-03
Improved: 2026-10-03 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete milestone; this plan is a read-only presentation expansion for already-landed V2 mechanics and does not claim `multi_hop_testimony_tracking` or any capability flag.

## Compatibility contract

This plan expands the read-only Godot observer and, where needed, thin presentation/projection adapters. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants stay intact. `WorldEngine` remains the only objective mutation authority. The client stays GET + observer WebSocket only. It never calls simulation control, admission, or any mutating route, and never sends a WebSocket payload.
2. No new capability flag. No `V2CapabilityFlags` slot, no `runner-config` bump, and no Alembic revision.
3. V1 regression gate stays green under flags-off and tracing-off. The client is not an experiment arm and must not be appended to `tests/unit/test_v1_regression_gate.py`.
4. No authoritative history schema bump. Stay on `observer-protocol-v1` and `observer-layout-v1`. Optional observer event fields and client `KNOWN_TYPES` may catch up to types already accepted by `src/observer/version.py` (`SEMANTIC_EVENT_TYPES`). Do not invent inverse/`AGENT_UN*` types.
5. No scripted emergence. Overlay colors, badges, and narrative highlights do not create graph edges, roles, groups, norms, traditions, or Myth objects as objective world facts. Cultural narratives remain owner-scoped ledgers + analysis detectors (see `.ai-factory/plans/v2-long-lived-cultural-narratives.md`).
6. No LLM involvement.
7. Experiments stay reproducible. Connecting the client, toggling overlays, changing perspective, or changing playback speed must not change seeds, event ids, or `exact_trajectory_hash`.
8. Optional cognition tracing stays outside the client. Do not request cognition-trace rows. Ordinary world view never shows utterance text or narrative content tokens. Research/debug overlays that surface experiment metadata must be clearly labeled and opt-in.

## Goal

Expand the existing Godot 4.7.2 Compatibility 2D observer so a researcher can watch V2 physical, social, communicative, and cultural mechanics that already exist in the simulation — without changing simulation semantics and without replacing the later full research/debug UI.

```text
Objective ObserverFrame (locations, agents, items, resources, structures, artifacts, season, weather, hazards)
  + optional researcher overlays (SUBJECTIVE / ANALYTICAL)
  + optional selected-agent perspective projections
  -> Godot world view / effects / overlays
```

Locations remain logical graph nodes. Structures and agents belong to locations. Any exact visual position inside a location is presentation-only and never written back.

## Current gap (locked baseline)

Already on the Python observer wire / contracts, but incomplete or missing in Godot:

| Area | Server / Python today | Godot today |
| --- | --- | --- |
| Structures + storage integrity | `ObserverWorldState.structures`, `STRUCTURE_*`, `ITEM_STORED` | not parsed / not painted |
| Harvest / craft / build / repair / store events | in `SEMANTIC_EVENT_TYPES` + `adapt.py` | absent from `KNOWN_TYPES`; fall through as generic activity / unknown |
| Season / weather / hazards / scarcity | frame + location paint + some events | mostly present; scarcity and event polish incomplete |
| Artifacts | frame + object layer + artifact events | present; keep objective-only (no interpretation as truth) |
| Relationships | `GET .../observer/agents/{id}/relationships` (`subjective_debug`) | route unused by client |
| Territorial claims / spatial analytics | claim + analytics overlays | present; keep evidence-class labels |
| Subjective labels / perspective | labels route + `PerspectiveControl` | labels only; not a full perspective mode |
| Metric catalog | `GET .../metrics` then `.../metrics/{set}/{family}` | analytics overlay assumes a caller-supplied `metric_set_id` |
| Groups / norms / conventions / reputation | analysis metric families (aggregate / document) | missing overlays |
| Cultural narrative hops | owner `NarrativeLedger` on checkpoint; `cultural_narrative_lineage@1` is **aggregate only** | missing; cannot be driven by the aggregate metric alone |
| Communication strategy | runtime audits; `communication_strategy@1` is **aggregate only** | speech bubbles show type + other id only |
| Skills / teaching | world skill ledger + teaching inferred from speech/practice; no dedicated observer semantic types | activity label only when a known event fires |
| Agent-visible HTTP | `GET .../agents/{id}/observation` returns **counts only** (`AgentVisibleOut`) | not usable as a known-artifact perspective payload |

## Design Decisions (locked)

### Platform and architecture

- **Target.** Godot 4.7.2 stable, GDScript, 2D, Compatibility renderer, web-compatible features only (`HTTPRequest`, `WebSocketPeer`; no `Thread`, GDExtension, C#, native sockets). Continue under `clients/godot-observer/`.
- **Read-only observer architecture.** Ordinary playback continues to consume `observer-protocol-v1` frames/events. Researcher overlays and perspective data come from separate GET projections. Never derive hidden agent knowledge client-side from researcher-only payloads.
- **No simulation semantics change.** Do not alter `WorldEngine` admission, event meanings, perception, cognition policies, or experiment trajectories. Presentation adapters may project committed facts; they must not invent facts.
- **Protocol version stays `observer-protocol-v1`.** Catch the client up to semantic types and optional event fields already accepted server-side (`recipe_id`, `structure_id`, `artifact_id`, `season`, `temperature_band`, `hazard_kind`). Add optional public-safe `declared_confidence_band` on `ObserverEvent` (speaker-declared band only; omitted when null). Reject presentation-instruction fields (`pixels`, `sprite`, `animation`, `dx`, `dy`).
- **Locations are authority for membership.** Structures, agents, ground items/resources/artifacts are painted from their `location_id` (or holder). Slot/`local_x`/`local_y` remain presentation anchors only.

### Evidence classes (mandatory for overlays)

Every researcher overlay marker, legend entry, and inspector badge must carry exactly one evidence class:

| Class | Meaning | Examples |
| --- | --- | --- |
| `OBJECTIVE` | Committed world / observer frame fact | structure kind, hazard presence, artifact kind, weather, Talk/Ask/Told delivery edges |
| `SUBJECTIVE_TO_SELECTED_AGENT` | Projection for one selected owner | relationships, territorial claims, subjective location labels, owner narrative-ledger hops |
| `ANALYTICAL_INFERRED` | Analysis/metric inference after the fact | candidate groups, territorial pattern metrics, norm/convention candidates, narrative aggregate detectors, per-event communication-strategy audit categories |

Never display an inferred group, norm, convention, tradition, reputation aggregate, Myth, or deception category as objective physical truth. UI copy and theme tokens must make the class unmistakable (legend + badge + log line). Prefer the short on-screen labels **OBJECTIVE**, **SUBJECTIVE**, **ANALYTICAL**.

### Metric catalog discovery (locked)

Analytical metric overlays must resolve a `metric_set_id` before any family GET:

1. `GET /v1/simulations/{run_id}/metrics` (`objective_inspection`)
2. Pick a catalog entry that lists the needed family (deterministic: prefer newest / first matching set; log the choice)
3. `GET /v1/simulations/{run_id}/metrics/{metric_set_id}/{metric_family}`

Empty catalog or missing family → empty overlay + `overlay_unavailable` (do not invent documents). Reuse this helper for `spatial_control`, group/norm/convention/reputation families, narrative aggregate badges, and communication-strategy aggregate panels.

Exact family path tokens (examples): `spatial_control`, `emergent_group_formation`, `emergent_social_norms`, `persistent_social_conventions`, `distributed_reputation`, `cultural_narrative_lineage`, `communication_strategy`, `cultural_transmission`, `skill_learning`.

### Physical / world visualizations

Paint from the objective frame and known semantic events:

- **Skills / activity.** Show short activity indications on agent tokens for production/practice events (`RESOURCE_HARVESTED`, `CRAFT_STARTED`, `ITEM_CRAFTED`, `STRUCTURE_BUILT`, `STRUCTURE_REPAIRED`, `ITEM_STORED`, search/move/rest/etc.). Do not invent a skill meter from researcher metrics in ordinary view.
- **Teaching interactions.** No dedicated teaching semantic type. Teaching appears only under an ANALYTICAL/SUBJECTIVE research overlay from projection/metrics (`cultural_transmission@1` or owner teaching projection), never as invented objective geometry and never by parsing utterance text client-side.
- **Harvesting / crafting / building / repair / storage.** Dedicated effect actions + event-log phrases + inspector fields (`recipe_id`, `structure_id`, `resource_id`, `item_id`). Structures paint at their location with integrity/storage cues from `ObserverStructure`.
- **Tools.** Distinguish tool-like items via existing `ObserverItem.kind` / theme catalog mapping. No new world kind inventing.
- **Structures.** Parse `world.structures` in `models.gd`; paint in object/structure layer by `location_id`; integrity and `stored_quantity` in inspector.
- **Season / weather / scarcity / hazards.** Keep location tints; ensure environment events update cues and log phrases; scarcity outline remains quantity-driven from frame refresh.
- **External symbolic artifacts.** Keep objective glyphs from `kind` only. Marks/interpretation stay out of ordinary paint.

### Social overlays

Add an optional researcher overlay panel (toggleable; default off) for:

- relationships (SUBJECTIVE; existing relationships route)
- reputation (ANALYTICAL via `distributed_reputation` after catalog discovery — never objective friendship labels)
- candidate social groups (ANALYTICAL via `emergent_group_formation`)
- territorial claims (SUBJECTIVE; existing claim overlay)
- analytical territorial patterns (ANALYTICAL; `spatial_control` after catalog discovery)
- norm-related events (ANALYTICAL via `emergent_social_norms` — never WorldEngine rules)
- conventions/traditions (ANALYTICAL via `persistent_social_conventions`)
- communication flows (OBJECTIVE delivery edges from Talk/Ask/Told structure only; strategy categories stay research-labeled)

Reuse the claim/analytics/label overlay pattern: session GET → `overlay_payload` → dedicated Node2D layer → enable/disable without mutating the objective world snapshot.

Where no safe read-only projection exists yet, add **thin presentation adapters** under `src/observer/` and/or existing inspection/metrics routes. Prefer existing routes and metric catalog first; new routes remain read-only, capability-gated, and never feed cognition.

### Communication presentation

Ordinary world view:

- Keep speech bubbles as structural labels (semantic type + other agent id).
- Differentiate visual style for `AGENT_TALKED` / `AGENT_ASKED` / `AGENT_TOLD`.
- Adapt optional public-safe `declared_confidence_band` from speaker-declared utterance confidence (`confidence_band(...)`). That is not a strategy verdict.
- **Never** label intentional deception, exaggeration, or selective disclosure as such in the ordinary world view. A deceptive utterance must look like ordinary speech structurally.
- Ordinary bubbles must not read research audit payloads even when those payloads are already loaded.

Research/debug mode (opt-in, clearly labeled **ANALYTICAL** / experiment metadata):

- Use a thin per-event audit projection (`event_id → category`) for truthful / uncertain / refusal / selective disclosure / deliberate deception beside the event id.
- Aggregate `communication_strategy@1` rates may appear as a secondary ANALYTICAL summary only; they are not enough for per-event labels.
- Panel title and badge must say research/debug metadata, not world truth.
- Still do not print utterance text, proposition payloads, or narrative content tokens in logs.

### Cultural / narrative visualization

Lightweight, not the full research UI. Aligned with `v2-long-lived-cultural-narratives`:

- **No Myth objects.** No objective myth/legend/culture furniture on the map.
- **Hops (Alice → Bob → Carol)** come from a SUBJECTIVE owner narrative-ledger projection: variant ids, status, `carrier_agent_ids`, `location_ids`, `parent_variant_ids` / `merged_into_id`, opaque `transmission_root_id` / `source_event_id` / `last_communication_id`. **Do not** send story content tokens, fingerprints as display labels, or free-form narrative text to the client.
- **`cultural_narrative_lineage@1`** is ANALYTICAL aggregate detectors only (persistence/mutation/spread rates). It may badge a selected lineage; it must not invent speaker order.
- Selector empty + `narrative_overlay_unavailable` when ledger projection / metric set is absent.
- Highlight speakers, transmission order, locations, and related opaque event ids on the existing map/log only.

### Perspective mode

UI modes:

1. **Objective researcher view** (default) — ordinary frame + optional researcher overlays explicitly toggled.
2. **Selected agent perspective** — only display perspective data supplied by appropriate backend projection endpoints for that agent.

Locked for this plan (because `AgentVisibleOut` is counts-only):

- Perspective loads: subjective labels, relationships, territorial claims (and the SUBJECTIVE narrative-ledger projection when enabled).
- **Do not** treat `GET .../agents/{agent_id}/observation` as a known-artifact payload.
- Known-artifact / full observation perspective DTOs are out of scope unless a dedicated read-only observer projection is added later; do not invent them from researcher metrics.
- Clearing perspective removes SUBJECTIVE layers and restores objective captions.
- ANALYTICAL overlays remain independent researcher toggles (not “what the agent sees”).
- Capability failures show a clear reason code and leave objective view intact.

### Performance

At high playback speeds / dense ticks:

- Keep existing snap policy (`speed >= 8` or pending motions `> 3`).
- Coalesce trivial activity marks of the same type on the same entity within a short window.
- Cap concurrent speech bubbles; drop oldest nonessential bubbles first.
- Prioritize state correctness from frame refresh over effects.
- Skip nonessential particles/pulses when skip policy is active; still apply logical reducer updates (`died`, occupancy, activity string may update without tween).
- Log DEBUG counts: `effects_coalesced`, `speech_dropped`, `overlay_markers`.

### Logging

- GDScript: `[observer.<area>] message key=value` via `scripts/log.gd`; `palimpsest/log_level` defaults DEBUG.
- Python adapters/routes: `infrastructure.logging.get_logger` / existing observer loggers.
- DEBUG may include run id, tick, sequence, event id, semantic type, overlay kind, evidence class, reason codes, coalesced counts, metric_set_id, family id.
- INFO: overlay enable/disable, perspective enter/clear, narrative selection, metric catalog resolution, bootstrap of new fixture packs.
- Never log tokens, seeds, utterance text, story content tokens, fingerprints as payload surrogates, relationship score payloads, or belief/proposition text.

## Non-Goals

- Changing WorldEngine rules, cognition policies, or experiment hashes
- Claiming `multi_hop_testimony_tracking` or any `V2CapabilityFlags` slot
- Full research/debug UI replacement (memory/belief/emotion/cognition-trace browsers)
- Showing utterance text, proposition bodies, or narrative content tokens in ordinary view
- Displaying inferred groups/norms/traditions/Myths as objective map furniture
- Driving Alice→Bob→Carol hops from `cultural_narrative_lineage@1` aggregates alone
- Driving per-event deception labels from aggregate `communication_strategy@1` alone
- Using `AgentVisibleOut` counts as known-artifact perspective
- Client-side invention of agent knowledge from researcher metrics
- Native-only Godot features, new renderer, 3D, or protocol rename

## Commit Plan

- **Commit 1** (after tasks 1–2, 5–6): `feat(godot): paint V2 structures and production events`
- **Commit 2** (after tasks 3–4, 7–9): `feat(observer): metric catalog, audit projection, social overlays`
- **Commit 3** (after tasks 10–12): `feat(observer): speech research metadata, perspective, narrative hops`
- **Commit 4** (after tasks 13–15): `feat(godot): performance coalescing and V2 smoke fixtures`
- **Commit 5** (after tasks 16–17): `docs(observer): document V2 mechanics visualization`

## Tasks

### Phase 1: Wire audit and presentation contracts

- [x] Task 1: Align Godot protocol models with current `observer-protocol-v1` objective payload
  - Add `StructureModel` and parse `world.structures` in `clients/godot-observer/scripts/protocol/models.gd`.
  - Extend `EventModel` / `parse_event` for optional `recipe_id`, `structure_id`, `declared_confidence_band`, and other optional fields already emitted by `ObserverEvent.public_mapping`.
  - Expand `KNOWN_TYPES` to include production types already in `src/observer/version.py`: `RESOURCE_HARVESTED`, `CRAFT_STARTED`, `ITEM_CRAFTED`, `STRUCTURE_BUILT`, `STRUCTURE_REPAIRED`, `ITEM_STORED` (artifact/season/hazard types already present stay).
  - Keep `protocol_version == observer-protocol-v1`; unknown future types still log without throw.
  - LOGGING: DEBUG `parsed kind=...`; ERROR `parse_failed reason_code=...`; WARN on unknown type count in fixture runs.
  - Files: `clients/godot-observer/scripts/protocol/models.gd`, `tests/test_models.gd`, protocol fixtures under `clients/godot-observer/fixtures/protocol/`.

- [x] Task 2: Define evidence-class overlay contract and UI legend
  - Introduce a shared GDScript evidence-class enum/constants: `OBJECTIVE`, `SUBJECTIVE`, `ANALYTICAL` (wire values may be longer; on-screen labels stay short).
  - Add a small legend/control in the UI layer for overlay toggles and class badges.
  - Document mapping table in code comments only where needed; full prose in docs task.
  - LOGGING: DEBUG overlay toggle `overlay_toggled kind=... evidence_class=... enabled=...`.
  - Files: `clients/godot-observer/scripts/presentation/evidence_class.gd` (new), `scripts/ui/ui_layer.gd`, `scenes/ui/ui_layer.tscn`, theme tokens in `theme_catalog.gd`.

- [x] Task 3: Discover metric catalog and resolve `metric_set_id` for analytical overlays
  - Session helper: `GET /v1/simulations/{run_id}/metrics`, pick a set that contains the requested family, then `GET .../metrics/{metric_set_id}/{metric_family}`.
  - Deterministic selection rule when multiple sets match; log chosen `metric_set_id`.
  - Empty catalog / missing family → emit `overlay_unavailable` and paint nothing.
  - Refactor existing `request_analytics_overlay` to use this helper instead of requiring a hard-coded set id from UI.
  - LOGGING: INFO `metric_catalog_resolved family=... metric_set_id=...`; WARN `overlay_unavailable kind=... reason_code=...`.
  - Files: `clients/godot-observer/scripts/net/session.gd`, overlay UI wiring, `test_session_cursor.gd` / new catalog tests.
  - Depends on: Task 2

- [x] Task 4: Add thin ANALYTICAL communication-strategy audit projection (per-event)
  - Deliverable: read-only DTO mapping committed communication `event_id` → research category (veridical / uncertain_inference / not_asserted / deliberate_deception / memory_error / unmatched as locked by analysis).
  - Source: runtime `CommunicationIntentAudit` joined to committed occurrences (same classification spirit as `communication_strategy@1`, but per-event). Aggregate metric alone is insufficient.
  - Capability-gated research/debug route; never feeds cognition; never included in ordinary observer frames.
  - Ordinary speech path must not consume this DTO.
  - LOGGING: DEBUG `strategy_audit_projected count=...`; WARN unavailable; never log utterance text or atom tokens.
  - Files: new projector under `src/observer/` or inspection composition, `src/api/routes/` + schemas, unit tests, Godot session fetch for research panel only.
  - Depends on: Task 2

### Phase 2: Physical / world visualization

- [x] Task 5: Paint structures, tools, storage, and production effects
  - Structure markers at location centers/anchors from `world.structures` (kind, integrity band, stored_quantity cue).
  - Tool/item kind differentiation in object layer theme mapping.
  - Extend `event_router.gd` actions for harvest/craft/build/repair/store (and keep season/hazard/artifact).
  - Extend `effects_layer.gd` + `event_log.gd` phrases; inspector shows structure/recipe/resource ids when present.
  - Activity indications on agent tokens for these production/practice events.
  - LOGGING: DEBUG `structures_painted count=...`, `played type=...`, `effect_skipped ...`; WARN unknown production type if mismatch.
  - Files: `object_layer.gd` / structure helpers, `effects_layer.gd`, `event_router.gd`, `event_log.gd`, `inspector.gd`, `theme_catalog.gd`, `world_view.gd`, related tests.
  - Depends on: Task 1
  <!-- Commit checkpoint: tasks 1-2, 5-6 -->

- [x] Task 6: Environment scarcity / hazard / season presentation polish
  - Ensure frame refresh drives season/weather/band/hazard/depleted paints; event pulses remain nonessential under skip policy.
  - Scarcity: quantity `== 0` depleted outline remains; optional soft low-quantity cue only if quantity is on the objective frame (no invented thresholds from analysis).
  - LOGGING: DEBUG `environment_painted tick=... season=... hazard_count=... depleted_count=...`.
  - Files: `location_layer.gd`, `theme_catalog.gd`, `effects_layer.gd`, tests.
  - Depends on: Task 1

### Phase 3: Social overlay framework and projections

- [x] Task 7: Wire existing subjective/analytical territorial + relationship overlays into the panel
  - Relationships overlay from `GET .../observer/agents/{agent_id}/relationships` (SUBJECTIVE). Dimension scores as researcher edges/list — no friend/enemy labels.
  - Keep claim overlay SUBJECTIVE and spatial_control ANALYTICAL; require legend badges; spatial_control uses Task 3 catalog discovery.
  - Session methods + main/ui wiring; disable cleanly on capability errors.
  - LOGGING: INFO overlay fetch ok/fail with reason codes; DEBUG marker counts; never log raw score payloads at INFO.
  - Files: `session.gd`, `main.gd`, `ui_layer.gd`, new/extended overlay scripts, `test_session_cursor.gd` / overlay tests.
  - Depends on: Task 2, Task 3

- [x] Task 8: Project owner narrative ledger hops for SUBJECTIVE story selection
  - Thin read-only projection from owner runtime checkpoint `cultural_narratives` / `NarrativeLedger`.
  - Expose only: `variant_id`, `status`, `origin`, `carrier_agent_ids`, `location_ids`, `parent_variant_ids`, `merged_into_id`, opaque `transmission_root_id` / `source_event_id` / `last_communication_id`, strength band if useful. **No** content tokens, fingerprints as labels, or free-form narrative text.
  - Evidence class SUBJECTIVE; capability `subjective_debug`. Empty ledger → empty selector.
  - Must not import analysis into cognition; projection is read-only presentation.
  - LOGGING: DEBUG `narrative_ledger_projected owner_id=... variant_count=...`; WARN unavailable; never log content tokens/fingerprints at INFO.
  - Files: `src/observer/` projector, API route/schemas, unit tests, Godot session GET.
  - Depends on: Task 7

- [x] Task 9: Add candidate group / norm / convention / reputation overlay adapters
  - Resolve `metric_set_id` via Task 3, then fetch families: `emergent_group_formation`, `emergent_social_norms`, `persistent_social_conventions`, `distributed_reputation`.
  - Render with **ANALYTICAL** badges and distinct non-physical styling (dashed/halo/list), never as solid objective zone ownership.
  - Reputation: researcher overlay only; no objective morality paint on tokens.
  - Missing documents → empty state + `overlay_unavailable` — do not synthesize.
  - LOGGING: DEBUG `analytical_overlay kind=... marker_count=...`; WARN `overlay_unavailable kind=... reason_code=...`.
  - Files: Godot overlay scripts + session GETs, optional thin DTO adapters if metric documents are awkward to paint, unit tests.
  - Depends on: Task 3, Task 7
  <!-- Commit checkpoint: tasks 4-9 -->

### Phase 4: Communication, perspective, narrative highlight

- [x] Task 10: Improve speech presentation without revealing deception in ordinary view
  - Visual differentiation for talk/ask/tell; show optional `declared_confidence_band` when present (public-safe).
  - Wire Python `adapt.py` / contracts / `ObserverEventOut` for optional `declared_confidence_band`.
  - Research/debug panel: fetch Task 4 per-event audit DTO; show categories beside event id with ANALYTICAL / experiment-metadata labeling.
  - Ordinary bubbles must not show deception (or any audit category) even if the research panel has the payload loaded.
  - Optional secondary aggregate rates from `communication_strategy` metric via Task 3 — summary only.
  - LOGGING: DEBUG `speech_shown type=...`; research panel DEBUG `strategy_meta event_id=... category=...` without utterance text.
  - Files: `adapt.py`, `contracts.py`, `observer_schemas.py`, `effects_layer.gd`, `event_router.gd`, research panel script, tests.
  - Depends on: Task 1, Task 2, Task 4

- [x] Task 11: Harden perspective mode (objective vs selected agent)
  - Perspective control switches mode; selected agent loads only: labels, relationships, claims, and (when toggled) SUBJECTIVE narrative-ledger projection from Task 8.
  - Objective mode clears SUBJECTIVE layers.
  - Do **not** call `GET .../agents/{id}/observation` for known artifacts (`AgentVisibleOut` is counts-only).
  - ANALYTICAL overlays remain researcher toggles independent of perspective.
  - LOGGING: INFO `perspective_entered agent_id=...` / `perspective_cleared`; DEBUG which projections were requested.
  - Files: `perspective_control.gd`, `main.gd`, `session.gd`, `world_view.gd`, label/claim/narrative overlays, tests.
  - Depends on: Task 7, Task 8, Task 10

- [x] Task 12: Lightweight cultural narrative transmission highlighter
  - Narrative selector populated from Task 8 SUBJECTIVE ledger projection (variant ids / carriers / locations / parents).
  - Highlight speakers and order from `carrier_agent_ids` (and parent/merge links where useful), locations from `location_ids`, related opaque event ids in the log.
  - Optional ANALYTICAL aggregate badges from `cultural_narrative_lineage` via Task 3 — never invent hops from aggregates.
  - No Myth furniture; empty/unavailable path mandatory.
  - LOGGING: INFO `narrative_selected id=...`; DEBUG hop count / highlighted entity counts; WARN unavailable; no content tokens/fingerprints at INFO.
  - Files: narrative overlay/UI scripts, session GET, `event_log.gd` focus hooks, tests.
  - Depends on: Task 3, Task 8, Task 11
  <!-- Commit checkpoint: tasks 10-12 -->

### Phase 5: Performance, fixtures, docs

- [x] Task 13: High-speed coalescing and speech/effect budgets
  - Extend `playback.gd` / effects policy: coalesce trivial same-entity activity marks; cap bubbles; skip nonessential pulses when `skip`; keep reducer state correct.
  - LOGGING: DEBUG `effects_coalesced count=...`, `speech_dropped count=...`, `motion_skipped ...`.
  - Files: `playback.gd`, `effects_layer.gd`, `test_playback.gd`, related tests.
  - Depends on: Task 5, Task 10

- [x] Task 14: Teaching / skills researcher overlays only
  - Do **not** re-implement activity cues (owned by Task 5).
  - Optional researcher overlays from `cultural_transmission` / `skill_learning` metrics via Task 3, or owner teaching projection if added as a thin read-only DTO.
  - Label ANALYTICAL/SUBJECTIVE correctly. No client-side teaching detection from utterance text.
  - LOGGING: DEBUG overlay marker counts; WARN unavailable.
  - Files: overlay/session pieces, tests.
  - Depends on: Task 3, Task 9, Task 11

- [x] Task 15: Visual smoke fixtures for new V2 mechanics
  - Add protocol event fixtures for harvest/craft/build/repair/store (+ any missing environment ones).
  - Extend `fixtures/smoke/` with session coverage for structures, artifacts, season/hazard/scarcity, production actions, overlay toggles (payload stubs including metric catalog miss), narrative hop stub (ledger-shaped, no content tokens), strategy audit stub, and high-speed coalescing case.
  - Keep Play Fixture path working offline without socket.
  - LOGGING: INFO fixture pack applied; DEBUG event counts per pack.
  - Files: `clients/godot-observer/fixtures/**`, `fixture_player.gd` if needed, `test_fixture_playback.gd`, `test_event_router.gd`, structure paint tests.
  - Depends on: Tasks 5–14
  <!-- Commit checkpoint: tasks 13-15 -->

- [x] Task 16: Docs checkpoint via `/aif-docs`
  - Update `docs/godot-observer.md` and `docs/observer.md` for: V2 physical visuals, overlay evidence classes, metric catalog discovery, perspective limits (`AgentVisibleOut` counts-only), communication ordinary vs per-event research audits, narrative ledger hops vs aggregate lineage metric, performance policy, fixture packs, allowed GET routes.
  - Keep README as landing pointer only.
  - LOGGING: n/a for docs prose; implementation logs remain as above.
  - Files: `docs/godot-observer.md`, `docs/observer.md`, README link only if missing.
  - Depends on: Task 15

- [x] Task 17: Verification gate for presentation-only safety
  - Confirm no `src/` import of `clients/godot-observer`.
  - Confirm ordinary view cannot display deception category from loaded research payloads.
  - Confirm analytical group/norm overlays cannot paint without ANALYTICAL badge and cannot replace objective zone ownership.
  - Confirm narrative hops are not invented from `cultural_narrative_lineage` aggregates alone.
  - Confirm V1 regression gate untouched / still green conceptually (no new gate membership).
  - Run Godot protocol test runner scripts and relevant Python observer adapter unit tests.
  - LOGGING: INFO verification summary counts; ERROR on any leak assertion failure.
  - Files: tests under `clients/godot-observer/tests/`, `tests/unit/` observer adapter tests as touched.
  - Depends on: Task 16
  <!-- Commit checkpoint: tasks 16-17 -->

## Implementation notes for `/aif-implement`

- Prefer extending existing layers (`object_layer`, `effects_layer`, `claim_overlay`, `analytics_overlay`, `label_overlay`, `session.gd`) over inventing a second world stack.
- When adding Python projectors, keep them in `observer` / API composition boundaries: no engine import, no private `world._*` from observer, no analysis→cognition path.
- Metric overlays must tolerate absent catalogs and absent metric documents.
- Narrative content tokens and communication atom tokens stay off the wire for presentation DTOs used here.
- Teaching/skills without dedicated semantic types must not be faked from free text.
- Preserve web export constraints from prior Godot plans.
- Cross-read `.ai-factory/plans/v2-long-lived-cultural-narratives.md` when implementing Tasks 8 and 12.

## Next steps

Plan refined with 17 tasks.
Plan file: `.ai-factory/plans/v2-godot-observer-mechanics-viz.md`

To start implementation, run:
`/aif-implement`
