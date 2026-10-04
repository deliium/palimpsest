# Implementation Plan: Researcher-Oriented V2 Web UI

Branch: none (`git.create_branches=false`; current branch `main`)
Created: 2026-10-04
Improved: 2026-10-04 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete milestone; this plan adds a complementary researcher web UI over already-shipped inspection, metrics, debugger, branch, and matrix surfaces without owning `multi_hop_testimony_tracking` or any new capability flag.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M6 — Remaining V2 Capability Flags
INFO [aif-plan] mode=ultra treated as full (richer plan); remaining args describe the feature
INFO [aif-plan] resolved plan file: .ai-factory/plans/v2-researcher-web-ui.md (format=slug)
INFO [aif-plan] plan name prefix v2- applied per user request; git.create_branches=false so stem is description slug
INFO [aif-improve] applied refinement: inspect-scoped run index; metadata-safe graph summaries; mount /research before /; lock Svelte; per-capability auth slots; SelfModel projection (not checkpoint row); observer relationships for social graph; matrix FS allowlist; same-origin iframe degrade; merge experiment stats into analytics; closed view allowlist; fix graph/run-list dependencies

## Downstream V2 plan contract

This plan must satisfy `docs/architecture.md` Downstream V2 plan contract:

1. V1 invariants intact. `WorldEngine` remains the only objective mutation authority. The Research UI is read-oriented presentation + optional control-plane actions already exposed by `/v1` (list/status; never invents world truth).
2. No new `V2CapabilityFlags` slot. Do **not** own `multi_hop_testimony_tracking`. No runner-config bump required for the UI itself.
3. V1 regression gate stays green under flags-off and tracing-off. Do not append Research UI routes or client smoke to `tests/unit/test_v1_regression_gate.py`.
4. Prefer no `observer-protocol-v1` rename. Additive optional deep-link query params and `/research/` static mount are allowed. Keep `/v1` stable; do not introduce `/v2` HTTP routes unless a response shape cannot be additive.
5. No scripted emergence. Inferred groups/norms/conventions/community structure must render as **research inference** / analytical results — never as objective world facts.
6. No LLM → world shortcuts. The UI never converts LLM text into commands.
7. Experiments stay reproducible. Opening the Research UI, seeking, embedding Godot, or comparing forks must not change seeds, event ids, or `exact_trajectory_hash`.
8. Optional cognition tracing stays outside the objective fold. Decision-trace views consume existing debugger / cognition-trace GETs under `subjective_debug`.
9. Observed metrics stay separate from agent-visible state. Metric documents, phenomenon panels, and matrix summaries remain analysis-only chrome labeled as research inference.

## Goal

Ship a researcher-oriented **V2 web UI** for analysis and debugging that answers:

> Why did it happen, and what patterns emerged?

It is complementary to the Godot graphical observer, which answers:

> What happened in the graphical world?

**Do not** rebuild the RimWorld-like world renderer in the Research UI.

### Responsibility split (locked)

| Surface | Owns | Must not own |
| --- | --- | --- |
| Godot Observer (`clients/godot-observer/`, `/`) | Spatial world presentation, timeline seek, live/replay, compact Why? inspector | Experiment matrices, statistical dashboards, multi-graph analysis chrome |
| Research UI (`clients/research-ui/`, `/research/`) | Run list, matrices, graphs, subjective ledgers, metrics, fork compare, decision traces, deep links | Authoritative world rendering, tick mutation, inventing emergence |

### Feature coverage (MVP of this plan)

- Run list (inspect-capable discovery)
- Experiment matrix overview
- Simulation metadata
- Social graph
- Relationship graph
- Memory graph
- Belief graph
- Self-model
- Goals
- Emotional state
- Theory of Mind
- Group/community analytics
- Territorial analytics
- Norm/convention metrics
- Cultural narrative lineage
- Cognitive decision traces
- Objective vs subjective event comparison
- Experiment statistics (per-run metric catalog subsection)
- Forked run comparison
- Bidirectional deep links with Godot (`run_id`, `tick`, `event_id`, `agent_id`)
- Optional adjacent/embed view of the Godot Web observer (loose coupling; same-origin iframe with new-tab fallback)

## Baseline already landed (do not rebuild)

| Layer | Status |
| --- | --- |
| Run list / status | `GET /v1/simulations`, `GET /v1/simulations/{run_id}` (`simulation_control` only today) |
| Objective inspection | world / events / agent-visible / experimental metadata / metrics |
| Subjective debug pages | memories / beliefs / relationships are **count-only** on `SubjectivePageOut`; territorial-claims returns heads |
| Observer relationships | `GET .../observer/agents/{agent_id}/relationships` returns dimension summaries (`subjective_debug`) |
| Observer presentation | Godot Web at `/` via `PALIMPSEST_PRESENTATION_WEB_ROOT` (mounted last in `create_app`) |
| Causal debugger HTTP | `/v1/.../debugger/*` (`subjective_debug`) |
| Branch lineage + compare | `/v1/.../branches*`, `POST .../branches/compare` |
| Deep-link parser | `observer.debugger_state.DebuggerDeepLinkState` (`run_id`, `tick`, `event_id`/`sequence`, `agent_id`, `debugger`) |
| Godot advanced replay | `switch_run`, actor\|target `agent_id` filter, branch panel (presentation-only) |
| Matrix CLI | `palimpsest-matrix` / filesystem `experiment-matrix-v1` (no HTTP today) |
| Metric families + phenomenon panels | analysis-only; HTTP catalog/document already exists |
| Epistemic chrome in Godot | `EvidenceClass` (3) + debugger artifact kinds (6) |
| Auth | Single header `x-palimpsest-token` / Bearer; **per-capability secrets** (`api_control_credential`, `api_inspection_credential`, `api_agent_visible_credential`, `api_debug_credential`) |

### Known gaps this plan closes

1. No production Research UI client (docs currently say “no production frontend”).
2. No inspect-scoped run discovery when auth is on (`GET /v1/simulations` requires `simulation_control`).
3. No HTTP for goals / emotional state / self-model projection / ToM / group / norm / convention / narrative ledger summaries (checkpoint fields exist; only territorial claims are projected today).
4. Memory/belief inspection pages expose counts only — insufficient for graphs; need metadata-safe id/edge summaries.
5. No shared Research UI deep-link contract or Godot → Research outbound navigation.
6. Matrix overview/statistics are CLI/filesystem-only; UI needs a read-only path without `api` importing `analysis` and without `research_runner` importing `api`.
7. Finer epistemic visual taxonomy than Godot’s three wire classes for researcher chrome.

## Locked scope decisions

1. **Client placement.** New tree `clients/research-ui/` — not a Python package. `src/` must not import it. Mirror the Godot pattern: build artifacts are served by the API from a configured directory.
2. **Mount path + order.** Serve the Research UI at **`/research/`** (SPA fallback to `index.html`). Godot keeps **`/`**. **Mount `/research/` before the catch-all `/` presentation mount.** Same origin for `/v1`, `/health`, `/version`, observer WS. No second reverse proxy.
3. **Frontend stack (locked).** **Svelte + Vite + TypeScript** (strict). Graph rendering via Cytoscape.js (or equivalent) for research graphs only — never a tile world. No Godot, no WebGL world map.
4. **Epistemic chrome taxonomy (UI-closed).** Every panel, node, edge, and metric chip must carry exactly one of:

   | UI class | Meaning | Never presented as |
   | --- | --- | --- |
   | `objective_world` | Committed world / journal truth | agent belief |
   | `agent_observation` | Agent-visible projection | world authority |
   | `agent_memory` | Owner episodic / reconstructed memory | objective event |
   | `agent_belief` | Semantic belief / self-model / goals / emotion / ToM attitudes | objective fact |
   | `agent_imagination` | Imagined futures / prospective branches | committed history |
   | `counterfactual` | Agent counterfactual scenarios **or** research fork interventions (label which) | parent-run truth |
   | `research_inference` | Metric documents, phenomenon panels, matrix stats, inferred groups/norms/conventions/community | objective world truth |

   Map from existing server signals (`EvidenceClass`, debugger artifact kinds, `EvidenceStage`, metric/overlay kinds). Extending Godot’s three wire classes is **presentation-only** in the Research UI; do not rename `observer-protocol-v1`.
5. **Analytical labeling rule.** Group formation, social norms, conventions, community structure, territorial concentration, cultural narrative aggregate rates, and any `support_band` panel **must** show `research_inference` chrome and copy such as “Analytical result” — never “World fact” / unlabeled group membership on the objective timeline. Owner ledger summaries from checkpoints remain `agent_belief` (subjective), visually separated from analytical metrics.
6. **Deep links (credential-free).** Shared parsing (Python + TS + Godot) around stable keys:

   | Param | Role |
   | --- | --- |
   | `run_id` | Required for run-scoped views |
   | `tick` | Optional seek |
   | `event_id` | Preferred event focus |
   | `sequence` | Intra-tick focus (“event N”) |
   | `agent_id` | Domain `AgentId` (owner / actor focus) |
   | `view` | Closed Research UI view allowlist (see Design Decisions) |
   | `debugger` | Godot-only: open Why? inspector |

   Reject credential-like query keys (reuse `api.security` / `_QUERY_SECRET_KEYS` policy). Tokens stay header / WS subprotocol only. Godot’s event-filter `agent_id` may be an **entity id** internally (advanced-replay plan); Research UI deep links always carry domain `AgentId` strings.
7. **Godot interoperability.** Research UI → Godot: open `/?run_id=…&tick=…&event_id=…&agent_id=…` (and `debugger=1` when opening Why?). Godot → Research UI: `OS.shell_open` / `JavaScriptBridge` to `/research/?…`. Optional adjacent pane: **same-origin iframe** to `/?…`; on bootstrap failure **degrade to new tab**. `postMessage` focus relay optional. No shared mutable store; no GDScript imports into the SPA. Align with shipped `switch_run` / deep-link seek semantics — do not reimplement ObserverSource replacement in the SPA.
8. **Matrix access.** Settings `PALIMPSEST_RESEARCH_MATRIX_ROOT`. List only **immediate child directories** that contain `manifest.json` with schema id `experiment-matrix-v1`. Serve allowlisted relative files only: `manifest.json`, `cells/<cell_id>.json`, `cells/<cell_id>.metrics.json`, `aggregate.json` (or the repo’s canonical aggregate filename), `metric-summary.json`. Path traversal fail-closed. Validate schema ids only. Do **not** import `analysis` from `api`. Do **not** run matrix batches from the UI.
9. **Inspect-scoped run index.** Add a read-only run listing under `objective_inspection` (reuse `RunListOut` or a thin envelope over the same `list_runs` port). Does not create/tick/configure. Control-plane `GET /v1/simulations` may remain for operators; Research UI default discovery uses the inspect route.
10. **Subjective projection routes.** Under `subjective_debug`, additive owner GETs for goals, emotional state, **self-model projection** (emergent `SelfModel` / identity over owner beliefs — not a persisted self-model row and not a second belief store), theory of mind, group formation, social norms, social conventions, cultural narratives. Pattern: `subjective_claims_document` / territorial-claims. Metadata-safe fields only.
11. **Graph wire data.** Do not treat count-only `SubjectivePageOut` as graph input. Prefer: (a) observer relationship summaries for relationship graphs; (b) new metadata-safe graph/summary DTOs (ids, targets, strengths/bands, opaque lineage refs) for memory/belief; (c) debugger lineage GETs for edge expansion when focused. No proposition/utterance/prompt bodies.
12. **Objective vs subjective comparison.** Reuse inspection events + agent-visible + graph/summary pages + drift/transmission **metric documents** when present. Do not move `MemoryDriftAnalysisService` into `api`.
13. **Fork compare.** Existing `POST /v1/simulations/branches/compare` + lineage GETs. Side-by-side timelines — not a dual Godot viewport.
14. **Control plane.** Default UX is inspect-first. Creating forks / ticking remains optional advanced actions behind `simulation_control`. No new mutation semantics.
15. **Auth UX.** Four in-memory (or sessionStorage) credential slots — control / inspection / agent_visible / debug — injected as `x-palimpsest-token` (or Bearer) **matching the route’s capability**. No OAuth-style refresh. Open-local when credentials unset (`PALIMPSEST_API_AUTH_REQUIRED` unset).
16. **Serving settings.** `PALIMPSEST_RESEARCH_WEB_ROOT` for the built SPA. Local `./scripts/api.sh` may leave it unset.
17. **Out of scope.** Owning `multi_hop_testimony_tracking`; rebuilding world renderer; `/v2` routes; Alembic revisions solely for UI; Kafka; replacing Godot; writing matrix cells from the browser; feeding UI analytics back into cognition; unified multi-token session refresh protocols.

## Design Decisions (locked)

### Package / trust boundaries

```text
clients/research-ui/     # Svelte SPA only; HTTP to /v1
api/                     # mount /research/ before /; additive inspection + matrix-fs + inspect run index
observer/                # shared deep-link + epistemic contracts (Python); no SPA imports
persistence/             # checkpoint / subjective summary helpers if needed (no analysis)
analysis/                # unchanged algorithms; consumed only via persisted metric docs / FS JSON
research_runner/         # still CLI-only; no api import
```

- `api` **must not** import `analysis` (`tests/architecture/test_analysis_isolation.py`).
- `research_runner` **must not** import `api`.
- `src/` **must not** import `clients/research-ui`.

### Closed `view` allowlist (deep-link)

```text
overview | graphs | agent | analytics | traces | compare | matrix
```

Unknown `view` → WARN client/server parse → default `overview`. Reject empty `run_id` for run-scoped views; `matrix` may omit `run_id`.

### Navigation IA (single SPA)

```text
/research/                      → run list (inspect index)
/research/runs/:runId           → metadata + tabs
  tabs: overview | graphs | agent | analytics | traces | compare
/research/matrix                → matrix overview (configured root)
/research/matrix/:matrixId      → cells + stats
```

### Visual distinction

- CSS variables per epistemic class (color + pattern + text label). Prefer patterns/icons in addition to color.
- Forbidden: unlabeled “Group: Village A” on an objective timeline; inferred norms without `research_inference` badge.
- Counterfactual research forks labeled “Research fork” vs agent imagination labeled “Agent imagination”.

### Logging

Verbose structured logs at API boundaries and client debug hooks:

- API: route template, run_id, owner_id, counts, reason codes — never memory/belief/relationship/LLM payloads, tokens, seeds, or matrix cell config dumps.
- Client: console debug gated by `import.meta.env.DEV`; never persist tokens in query strings; sessionStorage for tokens is local-researcher only.

## Commit Plan

- **Commit 1** (after tasks 1–3): `feat(research-ui): scaffold Svelte SPA, static mount, and epistemic chrome contract`
- **Commit 2** (after tasks 3b–6): `feat(research-ui): inspect run index, metadata views, auth slots, and deep links`
- **Commit 3** (after tasks 7–10): `feat(api,research-ui): subjective projections, graph summaries, and research graphs`
- **Commit 4** (after tasks 11–13): `feat(research-ui): analytics, decision traces, and obj/subj comparison`
- **Commit 5** (after tasks 14–16): `feat(research-ui): matrix overview, Godot embed, and fork compare`
- **Commit 6** (after tasks 17–19): `test(research-ui): contracts, routes, docs, and smoke coverage`

Each checkpoint is a git commit on the current branch when those tasks complete. Do not squash at the end. `git.create_branches` is false.

## Tasks

### Phase 1: Scaffold + epistemic contract

- [x] Task 1: Scaffold `clients/research-ui` Svelte + Vite + TypeScript SPA
  - Deliverable: Initialize `clients/research-ui/` with lockfile, `vite` config (`base: '/research/'`), TypeScript strict mode, lint/test scripts, and a minimal shell layout (nav + main outlet). **Stack locked: Svelte.** Graph lib reserved for later tasks (Cytoscape.js or equivalent). No world canvas. Document `pnpm build` → `dist/` in `clients/research-ui/README.md`.
  - Logging: build scripts print INFO `research_ui_build_ok file_count=%s`; failures ERROR with reason codes only.
  - Files: `clients/research-ui/**`.

- [x] Task 2: Mount Research UI static files from FastAPI (before Godot `/`)
  - Deliverable: Add `PALIMPSEST_RESEARCH_WEB_ROOT` settings; mount SPA at `/research/` with HTML5 history fallback **before** `mount_presentation` catch-all `/`. Do not steal `/v1`, `/health`, `/version`. Extend `GET /version` with a boolean/string field such as `research_ui_configured` (additive; keep existing keys). Unit-test: `/research/` and `/v1` win over presentation; missing index skips mount with ERROR reason.
  - Logging: INFO `research_static_mounted path_suffix=research file_count=%s`; WARN/ERROR `research_static_missing` / `research_static_skipped reason_code=%s`.
  - Depends on task 1.
  - Files: `src/infrastructure/settings.py`, `src/api/research_static.py` (prefer sibling to `presentation_static.py`), `src/api/app.py`, `src/api/routes/version.py` / `version_payload`, tests.

- [x] Task 3: Define shared epistemic chrome + deep-link contracts
  - Deliverable: Python module `observer/research_ui_state.py` (keep `debugger_state.py` for Godot debugger params; share secret-key rejection with `api.security` / `_QUERY_SECRET_KEYS`) with: (a) closed UI epistemic class constants; (b) mapping helpers from `EvidenceClass` / debugger artifact kinds / overlay kinds → UI class; (c) `ResearchUiDeepLinkState` parser/builder for `run_id`, `tick`, `event_id`, `sequence`, `agent_id` (domain `AgentId`), `view` (**closed allowlist** above) — reject secrets. Mirror in TS (`epistemic.ts`, `deeplink.ts`). Godot URL builder stubs for outbound Research links (Task 15 completes wiring). Tests: reject-token, require-run_id for run views, unknown `view` → default, analytical overlays → `research_inference`.
  - Logging: WARN `research_ui_state_rejected reason_code=%s`; DEBUG mapping in tests only.
  - Files: `src/observer/research_ui_state.py`, `src/observer/__init__.py` exports if needed, `clients/research-ui/src/epistemic.ts`, `clients/research-ui/src/deeplink.ts`, `tests/unit/test_research_ui_state.py`.

### Phase 2: Run discovery, metadata, auth, deep links

- [x] Task 3b: Inspect-scoped read-only run index
  - Deliverable: Add `GET` under `objective_inspection` that lists runs via the existing `list_runs` port (reuse `RunListOut` or a thin identical envelope). No create/configure/tick/stop. Keyset pagination + `api_max_page_size` caps match control list. Unit tests: inspect credential succeeds; control-only mutation routes unchanged; open-local when inspection secret unset.
  - Logging: INFO `route_inspect_run_list` with count only.
  - Depends on task 2 (router wiring conventions).
  - Files: `src/api/routes/inspection.py` (or dedicated router), `src/api/simulation_manager.py` reuse, tests.

- [x] Task 4: Run list + simulation metadata views
  - Deliverable: SPA pages call Task 3b inspect index (not control `GET /v1/simulations` by default) plus `GET .../observer/run`, `GET .../experimental`, `GET .../branch` when capable. Show lifecycle, ticks, experiment membership metadata (never seeds/condition values), optional fork lineage. Capability errors surface reason codes.
  - Logging: client DEBUG fetch status codes; no payload logs.
  - Depends on tasks 1–3, 3b.
  - Files: `clients/research-ui/src/views/RunList*`, `RunOverview*`, API client module.

- [x] Task 5: Per-capability credential UX (header-only)
  - Deliverable: Four local slots — `simulation_control`, `objective_inspection`, `agent_visible`, `subjective_debug` — stored in memory or sessionStorage. For each fetch, send `x-palimpsest-token` (or Bearer) with the **credential that matches that route’s capability**. Never put tokens in URLs, deep links, or iframe `src`. Document open-local default. Surface 401/403 reason codes (`missing_credential`, `invalid_credential`, `debug_disabled`). No OAuth refresh flow.
  - Logging: WARN client-side if a pasted URL contains banned secret keys; strip before navigation.
  - Depends on task 3.
  - Files: `clients/research-ui/src/auth*`, docs note in Task 19.

- [x] Task 6: Bidirectional deep-link application in the SPA
  - Deliverable: On boot, parse `window.location.search` via shared contract; route to the correct view; keep URL updated on tab/agent/event focus without credentials. “Open in World Observer” builds Godot `/?…` links (new tab or embed host).
  - Logging: DEBUG `research_ui_deeplink_applied run_id=%s view=%s` (ids only).
  - Depends on tasks 3–4.
  - Files: `clients/research-ui/src/deeplink.ts`, router, Godot link builder.

<!-- Commit checkpoint: tasks 1–3 → Commit 1; tasks 3b–6 → Commit 2 -->

### Phase 3: Subjective projections + graphs

- [x] Task 7: Additive subjective_debug projection routes for checkpoint ledgers
  - Deliverable: Owner GET summaries (closed schema versions) for: `goals`, `emotional-state`, `self-model` (**projection**: emergent `SelfModel` / identity over owner-scoped beliefs and `identity_cursor` — not a checkpoint `self_model` column and not a second belief store), `theory-of-mind`, `group-formation`, `social-norms`, `social-conventions`, `cultural-narratives`. Source from `owner_runtime_checkpoint` + simulation helpers patterned on `subjective_claims_document`. Return `availability=unavailable` when mode/flag off or checkpoint missing. Gate with `subjective_debug`. Metadata-safe fields only (ids, counts, strengths, bands, statuses). Subjective ledgers use `agent_belief` chrome in the client — never `research_inference`.
  - Logging: INFO route templates + head counts; never log propositions/narratives/utterances.
  - Depends on task 2.
  - Files: `src/api/routes/inspection.py`, `src/api/schemas.py`, `src/simulation/inspection.py` (or sibling projectors), tests.

- [x] Task 7b: Metadata-safe subjective graph / summary DTOs
  - Deliverable: Under `subjective_debug`, expose paginated summary endpoints (or additive fields) for memory and belief graph construction: opaque ids, created ticks, source/kind codes, strength/confidence bands, target ids, evidence/lineage ref ids — **no** proposition text, utterance bodies, prompts, or reconstruction narratives. Relationship graphs **reuse** `GET .../observer/agents/{agent_id}/relationships` (already has `items` + dimensions). Document that count-only `SubjectivePageOut` remains unchanged for existing clients. Unit tests prove no forbidden payload keys on the wire.
  - Logging: INFO counts only; DEBUG page sizes.
  - Depends on task 3, 7 (schema/logging conventions).
  - Files: `src/api/schemas.py`, `src/api/routes/inspection.py` and/or observer routes, persistence loaders, tests.

- [x] Task 8: Agent panel UI (self-model, goals, emotion, ToM)
  - Deliverable: Agent tab rendering Task 7 documents with `agent_belief` chrome. Empty/unavailable states explain flag/mode requirements without implying objective absence of social reality.
  - Logging: client DEBUG which panels unavailable + reason codes.
  - Depends on tasks 4, 7.
  - Files: `clients/research-ui/src/views/AgentPanel*`.

- [x] Task 9: Relationship + social graph views
  - Deliverable: Relationship graph from observer relationship summaries (`items` + dimensions) tagged `agent_belief`. Social/communication graph from bounded observer event pages (`Talked` / `Asked` / `Told` semantic types) tagged `objective_world` for delivery-only edges. No friend/enemy/leader labels. Cap nodes/edges with explicit truncation DEBUG.
  - Logging: DEBUG node/edge counts only.
  - Depends on tasks 3, 4, 7b.
  - Files: `clients/research-ui/src/graphs/social*`, `relationship*`.

- [x] Task 10: Memory + belief graph views
  - Deliverable: Build graphs from Task 7b summaries + debugger lineage GETs when `event_id`/`agent_id` focused. Epistemic classes: `agent_memory` vs `agent_belief`. Reconstructive nodes must not look like objective journal rows. Do **not** use count-only inspection pages as the sole data source.
  - Logging: DEBUG graph size + unavailable lineage reason codes.
  - Depends on tasks 3, 7, 7b.
  - Files: `clients/research-ui/src/graphs/memory*`, `belief*`.

<!-- Commit checkpoint: tasks 7–10 → Commit 3 -->

### Phase 4: Analytics, traces, objective vs subjective

- [x] Task 11: Analytics + per-run experiment statistics
  - Deliverable: Analytics tab loads metric catalog + family documents (`emergent_group_formation@1`, `spatial_control@1` / `territorial_concentration@1`, `emergent_social_norms@1`, `persistent_social_conventions@1`, `cultural_narrative_lineage@1`, phenomenon panels when present) **and** a per-run statistics subsection (document counts, availability, key scalars). All metric chrome = `research_inference`. Show `support_band` codes; forbid boolean “emerged” labels. Pair with subjective ledger summaries from Task 7 when debug-enabled, visually separated (`agent_belief` vs `research_inference`). Cross-run distributions remain matrix Task 14.
  - Logging: DEBUG metric family fetch status; never dump metric payloads to server logs.
  - Depends on tasks 4, 7.
  - Files: `clients/research-ui/src/views/Analytics*`.

- [x] Task 12: Cognitive decision trace view
  - Deliverable: Consume existing debugger GETs (`causal-trace`, invocations, lineage) to render the researcher chain with epistemic classes mapped from debugger artifact kinds (`observation` → `agent_observation`, memories → `agent_memory`, beliefs/ToM/goals/emotion → `agent_belief`, imagined → `agent_imagination`, counterfactuals → `counterfactual`, action → `objective_world`). Link “Open tick/event in World Observer”.
  - Logging: client DEBUG stage availability only.
  - Depends on tasks 3, 6.
  - Files: `clients/research-ui/src/views/DecisionTrace*`.

- [x] Task 13: Objective vs subjective event comparison
  - Deliverable: Side-by-side view for a focused `(run_id, tick, event_id|sequence, agent_id)`: objective event summary + agent-visible observation metadata + memory/belief summary links (Task 7b) + optional drift/transmission metric snippets when documents exist. Each column locked to its epistemic class. Unavailable sources show reason codes — never fabricate alignment.
  - Logging: DEBUG which columns available.
  - Depends on tasks 4, 10, 12.
  - Files: `clients/research-ui/src/views/ObjSubjCompare*`.

<!-- Commit checkpoint: tasks 11–13 → Commit 4 -->

### Phase 5: Matrix, Godot embed, forks

- [x] Task 14: Read-only matrix filesystem API + overview UI
  - Deliverable: Settings `PALIMPSEST_RESEARCH_MATRIX_ROOT`. Routes e.g. `GET /v1/research/matrices` and `GET /v1/research/matrices/{matrix_id}/…` (under `/v1`, not the static `/research/` mount). List only immediate child directories with valid `manifest.json` (`experiment-matrix-v1`). Serve allowlisted files only (manifest, cell refs, metrics sidecars, aggregate, metric-summary). Path traversal fail-closed (`resolve` under root). Capability: `objective_inspection`. SPA matrix overview + cell table + aggregate/summary charts. Do not start runs from this UI. Never log seeds/full configs.
  - Logging: INFO list counts; WARN `matrix_fs_rejected reason_code=%s`.
  - Depends on tasks 2, 4.
  - Files: `src/api/routes/research_matrix.py`, settings, SPA matrix views, tests.

- [x] Task 15: Godot outbound deep links + optional same-origin embed
  - Deliverable: In Godot, “Open in Research UI” actions (selected event / agent / tick) building `/research/?run_id&tick&event_id&agent_id&view=…` via `JavaScriptBridge` (Web) or `OS.shell_open` (desktop), using Task 3 builders. Research UI optional adjacent pane: **same-origin** iframe to `/?run_id=…` (threads off / no COOP-COEP required). On iframe bootstrap failure, degrade to new tab. Optional `postMessage` focus relay; URL reload on iframe is enough. No shared JS imports. Do not reimplement `switch_run` in the SPA.
  - Logging: Godot INFO `research_ui_link_opened`; SPA DEBUG embed load / `embed_fallback_new_tab`.
  - Depends on tasks 3, 6.
  - Files: `clients/godot-observer/scripts/**`, `clients/research-ui/src/embed/*`, Godot tests for URL builder.

- [x] Task 16: Forked run comparison UI
  - Deliverable: UI over lineage list + `POST /v1/simulations/branches/compare` showing divergence ticks/event-kind deltas. Label research forks as research-intervention `counterfactual` chrome distinct from agent imagination. Link either side into Observer or Research views via deep links.
  - Logging: DEBUG compare response counts only.
  - Depends on tasks 4, 6.
  - Files: `clients/research-ui/src/views/ForkCompare*`.

<!-- Commit checkpoint: tasks 14–16 → Commit 5 -->

### Phase 6: Hardening, docs, verification

- [ ] Task 17: Unit/contract tests for epistemic mapping, mount order, matrix FS, graph wire safety
  - Deliverable: Pytest for deep-link secret rejection, epistemic mapping (analytical → `research_inference`), `/research/` mount-before-`/`, matrix path traversal rejection, inspect run index capability, new inspection/graph routes (available/unavailable), **no forbidden payload keys** on graph summaries. Keep `tests/architecture/test_analysis_isolation.py` green. Client unit tests for deeplink parse/build and class badge rendering. No default-pytest Docker/Godot launch.
  - Logging: assert WARN/INFO reason codes in API tests where applicable.
  - Depends on tasks 2, 3, 3b, 7, 7b, 14.
  - Files: `tests/unit/test_research_ui_*.py`, architecture suite (unchanged contracts), `clients/research-ui` test config.

- [ ] Task 18: Compose/dev wiring for built Research UI (optional smoke)
  - Deliverable: Document and, if practical, wire `PALIMPSEST_RESEARCH_WEB_ROOT` in `compose.dev.yaml` / scripts. Opt-in compose smoke that checks `/research/` returns `index.html` when built artifacts exist — mark `compose`, keep out of default pytest.
  - Logging: startup INFO when research root mounted.
  - Depends on task 2.
  - Files: `compose.dev.yaml` / scripts, optional `tests/compose/…`.

- [ ] Task 19: Documentation checkpoint (`/aif-docs` scope)
  - Deliverable: Add `docs/research-ui.md`; update `docs/research-api.md` (frontend exists; inspect run index; projection + graph summary routes; matrix FS; `/research/` mount order; per-capability auth); update `docs/godot-observer.md` (outbound Research links, same-origin embed + fallback); README table row; epistemic labeling rules and responsibility split. State explicitly that inferred groups/norms are analytical. Note count-only subjective pages vs new graph summaries.
  - Logging: n/a (docs).
  - Depends on tasks 1–18.
  - Files: `docs/research-ui.md`, `docs/research-api.md`, `docs/godot-observer.md`, `README.md`, `.ai-factory/DESCRIPTION.md` one-line surface note if accurate.

<!-- Commit checkpoint: tasks 17–19 → Commit 6 -->

## Risk table

| Risk | Mitigation |
| --- | --- |
| Researchers mistake metrics for world truth | Mandatory `research_inference` badges; copy review in Task 19 |
| `/` steals `/research/` | Mount `/research/` before presentation `/`; Task 17 mount tests |
| Inspect-only users cannot list runs | Task 3b inspect run index |
| Graphs built from empty count pages | Task 7b summaries + observer relationships |
| `api` imports `analysis` | Matrix FS + metric docs only; architecture tests |
| Token leakage via deep links / iframe | Shared secret-key rejection; Task 5; never tokens in `src` |
| Self-model treated as person class / second store | Task 7 projection wording + schema |
| Scope explosion into world renderer | Explicit non-goal |
| Matrix path traversal | Allowlist + resolve-under-root; Task 17 |
| Iframe WASM bootstrap flake | Same-origin only + new-tab fallback (Task 15) |

## Verification (implementer)

```bash
uv run --frozen --python 3.12.14 pytest \
  tests/unit/test_research_ui_*.py \
  tests/unit/test_api_inspection_routes.py \
  tests/architecture/test_analysis_isolation.py \
  tests/unit/test_v1_regression_gate.py -q

# Client (from clients/research-ui)
pnpm test && pnpm build
```

V1 regression gate must remain green flags-off and tracing-off.
