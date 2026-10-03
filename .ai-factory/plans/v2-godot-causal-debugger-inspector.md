# Implementation Plan: Godot Causal Debugger Compact Inspector

Branch: none (`git.create_branches=false`; current branch `main`)
Created: 2026-10-04
Improved: 2026-10-04 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete milestone; this plan is a presentation-only Godot integration over the already-shipped research causal debugger — it does not claim `multi_hop_testimony_tracking` or any new capability flag.

## Downstream V2 plan contract
This plan must satisfy `docs/architecture.md` Downstream V2 plan contract:

1. V1 invariants intact (WorldEngine authority, Observation trust, subjective ≠ objective fold, no CoT/payload logging, append-only history).
2. No new `V2CapabilityFlags` slot. Debugger remains observational; reserved/unowned flags stay default-off / fail-closed.
3. V1 regression gate stays green under flags-off **and** tracing-off. No debugger routes added to that gate.
4. Prefer no runner-config / observer-protocol / cognition-trace schema bump. Presentation labels and visual taxonomy live in the Godot client (and docs). Wire continues to use existing `stage_code` / lineage / `observer_focus` fields.
5. No scripted emergence.
6. No LLM→world shortcuts; Godot never invents causal stages or free-text rationales.
7. Experiments stay reproducible; opening Why?, seeking, or provenance drill-down must not change seeds, event ids, or `exact_trajectory_hash`.
8. Cognition traces remain outside `EvidenceManifest`. Debugger stays GET-only.

## Overview

Backend research causal debugger already ships (`simulation.causal_debugger`, lineage ports, `/v1/.../debugger/*` under `subjective_debug`, docs in `docs/research-causal-debugger.md`). Godot already has a minimal panel: event-log **Explain** → `GET` causal-trace → raw `stage_code` list → activate node → seek via `observer_focus`.

Researchers still need a **compact, researcher-facing inspector** that reads like structured artifacts — not wire codes and not chain-of-thought — for selections such as:

```text
Alice attacked Bob
```

This plan upgrades the Godot presentation layer only:

1. Replace **Explain** with **Why?**
2. Render a compact stage strip using researcher labels
3. Allow expansion into the full structured artifact list
4. Navigate referenced prior events (timeline seek **or** secondary provenance view) and return to the original decision
5. Visually distinguish objective vs subjective/imaginative/analytical artifact kinds so subjective content never looks like objective reality

**Out of scope:** duplicating assembler/resolver/lineage logic in GDScript; Research UI graphs/statistical dashboards; new Alembic tables; protocol rename; capability-flag ownership.

### Baseline already landed (do not rebuild)

| Layer | Status |
| --- | --- |
| `CausalDebuggerService` + assemble/resolve | done (`v2-research-debugger-observer-timeline`) |
| Lineage GET `/debugger/lineage/{kind}/{id}` | done (Godot does **not** call it yet) |
| Deep-link `debugger` query + seek | done |
| Minimal `debugger_panel.gd` + Explain button | done — presentation upgrade target |

### Compact strip (default)

Researcher-facing collapsed labels (presentation only; map from existing `stage_code`):

| Compact label | Wire `stage_code` sources |
| --- | --- |
| Observed | `observation` |
| Remembered | `relevant_memories` + `reconstruction` |
| Believed | `beliefs` + `theory_of_mind` |
| Felt | `emotional_state` |
| Wanted | `goals` |
| Expected | `imagined_futures` + `counterfactuals` |
| Decided | `selected_intention` |
| Acted | `action` |

Supporting nodes (`situation_model`, `budget_summary`) stay secondary/collapsed — never replace this strip order.

### Compact status rollup (locked)

For each compact cell over its child wire nodes:

1. If **any** child status is `available` → rollup `available`
2. Else pick the first matching status among children in this priority: `truncated` → `failed` → `skipped` → `unavailable`
3. Surface one child `reason_code` when the rollup is not `available` (stable pick: first child in wire order that contributed the chosen status)

### Expected chrome (locked)

Compact **Expected** folds imagination + counterfactual:

- Use artifact kind `counterfactual` if any child stage is `counterfactuals` with non-`unavailable` status, **or** CF id_refs / selection codes (`counterfactual` / `cf_*`) are present on those children
- Otherwise use `imagination`

### Expanded artifacts

Expanding a compact row (or an Expand-all control) reveals the full ordered researcher chain labels in **server `RESEARCHER_CHAIN_SEQUENCE` order** (Emotion before Goals — do not reorder to Goals-before-Emotion):

```text
Observation
Memories
Reconstructed memory
Beliefs
Emotion
Goals
Theory of Mind
Imagined futures
Counterfactuals
Intention
Action
```

These are labels for structured stored artifacts (counts, statuses, id refs, focus handles) — never private CoT, prompts, or proposition/narrative text bodies.

Wire `id_refs` arrive as JSON arrays of `[kind, value]` pairs; parse that shape only.

### Visual distinction taxonomy (presentation)

Extend Godot presentation (alongside existing OBJECTIVE / SUBJECTIVE / ANALYTICAL overlay classes) with a closed **debugger artifact kind** used only for inspector chrome:

| Kind | Typical stages / sources | Presentation intent |
| --- | --- | --- |
| `objective_event` | committed occurrence focus / Acted when tied to world event | solid, primary timeline language |
| `observation` | Observed / Observation | agent-visible projection chrome (not world truth badge) |
| `memory` | Remembered / Memories / Reconstructed memory | subjective recall chrome |
| `belief` | Believed / Beliefs / Theory of Mind | subjective attitude chrome |
| `imagination` | Expected / Imagined futures | clearly non-factual chrome |
| `counterfactual` | Counterfactuals | alternate-path chrome distinct from imagination |
| `analytical_inference` | lineage `prediction` / analysis-shaped refs if shown | researcher-inference chrome |

Rules:

- Subjective / imagination / counterfactual rows must not reuse the same solid “fact” treatment as objective events.
- Unavailable stages show status + reason codes, not empty success.
- Legend/tooltip copy must say these are structured artifacts, not ground truth.

### Closed id_ref → lineage kind map (locked)

Map wire `CognitionTraceRefKind` values to existing lineage GET kinds. Do not invent routes for unmapped refs.

| Wire `id_ref` kind | Lineage `kind` | Notes |
| --- | --- | --- |
| `memory` | `memory_derivation` | |
| `belief` | `belief_evidence` | |
| `semantic_belief` | `belief_evidence` | |
| `goal` | `goal_ancestry` | |
| prediction / CF subject ids | `prediction` | Only when the subject is a prediction/counterfactual id (not every `future` ref) |

- Unmapped wire kinds (`future` unless CF/prediction subject, `drive`, `emotion`, `command`, `intention`, `motive`, `claim`, `agent`, `invocation`, …): WARN `unmapped_debugger_id_ref` and skip — no lineage GET.
- API also exposes `communication` / `narrative` lineage kinds, but current cognition-trace ref kinds do not emit matching id_refs; do not invent client-side communication/narrative triggers in this plan.

### Navigation (locked dual affordances)

1. **Seek** (primary activation when `observer_focus` is present) — seek `(tick, sequence)` / highlight `event_id`; keep the debugger panel open and retain the primary causal-trace payload.
2. **Provenance** (separate control when a mapped `id_ref` exists) — `GET …/debugger/lineage/{kind}/{id}?owner_id=…` and render a compact secondary pane (ids, statuses, nested `observer_focus` only). No local reasoning. Never silently combine Seek + Provenance in one click.
3. **Return to original decision** — navigation stack (depth ≤8) keyed by the original causal-trace address; Back restores the stashed primary payload and clears the secondary pane (re-GET the same address only if the payload was discarded).

`owner_id` is `address.agent_id` from the causal-trace payload. If missing: WARN `owner_id_missing` and skip lineage — never guess from display names.

Capability `403` / missing `subjective_debug` continues to use `overlay_unavailable` — never an empty chain as “no cognition”.

## Design Decisions (locked)

1. **Godot is render + navigate only.** All causal assembly stays on the server. GDScript maps `stage_code` → compact/expanded labels and artifact kinds; it does not invent stages, merge evidence, or score causality.
2. **No wire/schema bump required.** Reuse `CausalTraceOut`, `observer_focus`, `id_refs`, and lineage routes. If a label/kind table needs a shared Python constant for docs/tests only, keep it presentation-documentation — do not rename `observer-protocol-v1`.
3. **Compact-by-default.** One small inspector panel; no graph canvas, no statistical dashboard, no Research UI duplication.
4. **Owner id for lineage** comes from the causal-trace address `agent_id` / actor already returned by the server — never guessed from display names.
5. **id_ref → lineage kind** uses the closed table above; unknown kinds WARN + skip.
6. **Return stack depth** ≤8 frames; dropping oldest with WARN/DEBUG log is acceptable.
7. **Rename UX affordance** from Explain → Why? (button text + docs + tests). Keep signal names stable where churn is unnecessary (`explain_requested` may remain internally).
8. **Expanded order** follows server `RESEARCHER_CHAIN_SEQUENCE` (Emotion before Goals).
9. **Dual affordances:** Seek vs Provenance are explicit and separate; never both from one activation.
10. **Session GETs with query** are required for lineage (`owner_id`); extend the session helper rather than hardcoding empty query dicts.

## Commit Plan

- **Commit 1** (after tasks 1–2b): `feat(godot): compact Why? causal debugger inspector chrome`
- **Commit 2** (after tasks 3–4): `feat(godot): debugger provenance navigation and return stack`
- **Commit 3** (after tasks 5–6): `test(docs): godot causal debugger inspector gates`

## Tasks

### Phase 1: Presentation contracts in Godot

- [x] Task 1: Add compact/expanded label map, artifact-kind taxonomy, and closed id_ref→lineage map
  - Deliverable: New presentation helper under `clients/godot-observer/scripts/presentation/` (e.g. `debugger_labels.gd`) that:
    - Maps every researcher-chain wire `stage_code` → expanded label (Observation, Memories, Reconstructed memory, Beliefs, Emotion, Goals, Theory of Mind, Imagined futures, Counterfactuals, Intention, Action)
    - Groups stages into the 8 compact strip labels (Observed…Acted) per Overview table (each of the 11 codes in exactly one group)
    - Maps stage_code → closed debugger artifact kind; Expected chrome helper implements the locked counterfactual-vs-imagination rule
    - Implements the locked id_ref.kind → lineage kind table; returns empty + WARN path for unmapped kinds (`unmapped_debugger_id_ref`)
    - Exposes short legend strings that explicitly mark non-objective kinds
  - Unit-test: all 11 chain codes covered; compact groups partition exactly; id_ref map covers mapped kinds and rejects unmapped kinds; Expected chrome rule cases.
  - LOGGING REQUIREMENTS: DEBUG unknown `stage_code` with reason `unmapped_debugger_stage`; WARN `unmapped_debugger_id_ref`; never log payload text. Levels via existing `ObserverLog`.
  - Files: `clients/godot-observer/scripts/presentation/debugger_labels.gd`, `clients/godot-observer/tests/test_debugger_labels.gd`, register in `tests/run_protocol.gd`
  - Dependencies: None

- [x] Task 2: Compact Why? inspector UI over existing causal-trace payload
  - Deliverable: Upgrade `debugger_panel.gd` / `.tscn` (and event-log affordance):
    - Rename visible **Explain** → **Why?**
    - Default view: compact strip of 8 labels with locked status rollup
    - Compact header shows `availability`, `ambiguity`, `address.agent_id`, tick/sequence/event_id — not a raw wire dump as the primary UI
    - Expand control reveals full ordered artifact rows in **server chain order** (Emotion before Goals), with expanded labels, status, counts, command/intention codes when present
    - Parse `id_refs` as arrays of `[kind, value]`; apply artifact-kind chrome (Expected uses locked chrome rule)
    - Keep `supporting_nodes` collapsed/secondary; never promote them into the compact strip
    - Preserve unavailable / capability-forbidden panels
    - Still server-driven: `open_payload` only renders JSON already fetched
  - LOGGING REQUIREMENTS: INFO `debugger_opened` / `debugger_closed` / `why_requested` with availability + node_count; DEBUG compact/expanded toggles and rollup reasons; WARN unmapped stages; no utterance/memory/belief text.
  - Files: `clients/godot-observer/scripts/ui/debugger_panel.gd`, `scenes/ui/debugger_panel.tscn`, `scripts/ui/event_log.gd`, `scenes/ui/event_log.tscn`, related `ui_layer` wiring if needed, update `tests/test_debugger_panel.gd` / `test_event_log.gd`
  - Depends on: Task 1

- [x] Task 2b: Session GET helper with query support for debugger routes
  - Deliverable: Extend `clients/godot-observer/scripts/net/session.gd` so debugger GETs can pass a query dict through `Urls.build_get` (today `_request_path` hardcodes `{}`). Keep capability tokens in the HTTP header only — never query-string credentials. Prefer a small shared helper used by causal-trace-by-cursor (already query-based) and upcoming lineage requests. Add a focused session/URL test that the lineage path includes `owner_id` when requested.
  - LOGGING REQUIREMENTS: DEBUG built route + query keys (not values that could be mistaken for secrets; `owner_id`/ids OK); ERROR/WARN `read_only` when non-GET; never log token material.
  - Files: `clients/godot-observer/scripts/net/session.gd`, `scripts/protocol/urls.gd` only if needed, `clients/godot-observer/tests/test_session_cursor.gd` or new `test_session_debugger.gd`, `tests/run_protocol.gd`
  - Depends on: Task 2

<!-- Commit checkpoint: tasks 1-2b -->

### Phase 2: Navigation — seek, secondary provenance, return

- [x] Task 3: Session client for lineage GET + inspector secondary pane
  - Deliverable: Add `session.request_debugger_lineage(kind, subject_id, owner_id)` using Task 2b query support: path `/v1/simulations/{run_id}/debugger/lineage/{kind}/{subject_id}` with query `owner_id=…`, header token only. Wire kind `causal_debugger_lineage` through `_on_http` overlay branch and `main.gd` / `ui_layer` the same way as `causal_debugger` (including `403` → `overlay_unavailable` / panel unavailable — never empty provenance as “no evidence”). Secondary pane lists lineage entries (entry id, status/reason, optional `observer_focus`) without graph layout. Require `owner_id` from trace `address.agent_id`; if missing, WARN `owner_id_missing` and skip. Use Task 1 closed id_ref map only.
  - LOGGING REQUIREMENTS: DEBUG lineage request keys (run_id, kind, subject_id, owner_id); INFO lineage opened with entry_count; WARN `owner_id_missing` / `unmapped_debugger_id_ref` / invalid kind; never log subjective text bodies.
  - Files: `clients/godot-observer/scripts/net/session.gd`, `scripts/main.gd`, `scripts/ui/ui_layer.gd`, `scripts/ui/debugger_panel.gd`, GDScript tests
  - Depends on: Tasks 1, 2, 2b

- [x] Task 4: Navigation stack — Seek vs Provenance vs return to original decision
  - Deliverable (locked UX):
    - **Seek:** primary activation / Seek control when `observer_focus` is present → existing `focus_requested` path; panel stays open; primary causal-trace payload remains stashed
    - **Provenance:** separate control when a mapped `id_ref` exists → lineage GET (Task 3) and push a nav frame; never silently Seek+Provenance together
    - **Return to decision:** pop stack / Back restores stashed primary payload (re-GET same address only if discarded) and clears secondary pane
    - Bound stack ≤8; WARN/DEBUG on overflow drop
  - LOGGING REQUIREMENTS: INFO `debugger_nav_push` / `debugger_nav_pop` / `debugger_return_to_decision` with depth + address ids; DEBUG seek vs lineage choice; WARN stack overflow drop.
  - Files: `clients/godot-observer/scripts/ui/debugger_panel.gd`, `scripts/main.gd` as needed, tests for round-trip: Why? → provenance → return; Why? → seek focus → primary decision still shown
  - Depends on: Tasks 2, 3

<!-- Commit checkpoint: tasks 3-4 -->

### Phase 3: Hardening and docs

- [x] Task 5: Tests for presentation safety and non-duplication
  - Deliverable:
    - Label/kind completeness + locked id_ref map + Expected chrome + rollup priority (Tasks 1–2)
    - Panel tests: compact labels; expansion in server chain order (Emotion before Goals); Why? affordance; unavailable/403 paths unchanged in meaning; seek does not clear primary payload
    - Navigation tests: lineage URL includes `owner_id`; `causal_debugger_lineage` wiring; return stack; Seek uses `observer_focus` only; Provenance is a separate path
    - Guardrails: no new Python assembler logic in Godot; no mutation routes; confirm existing `tests/architecture/test_causal_debugger_boundaries.py` still green; V1 regression gate untouched
    - Assert logs stay metadata-only (ids, counts, reason codes)
  - LOGGING REQUIREMENTS: Tests assert presence of key `ObserverLog` lines / reason codes; failure messages use stable codes.
  - Files: `clients/godot-observer/tests/*.gd`, `tests/run_protocol.gd`; Python architecture tests only if new edges appear (prefer none)
  - Depends on: Tasks 1–4 (incl. 2b)

- [x] Task 6: Documentation checkpoint (`/aif-docs`)
  - Deliverable: Update contributor docs:
    - `docs/godot-observer.md` — Why? flow; compact vs expanded labels; Emotion-before-Goals expansion order; status rollup; Expected chrome; artifact-kind distinction; locked id_ref→lineage map; Seek vs Provenance dual affordances; return-to-decision; 403/unavailable behavior; Research UI / analysis dashboards explicitly out of scope
    - `docs/research-causal-debugger.md` — short cross-link noting Godot presentation labels are client-side and must not be read as CoT
  - LOGGING REQUIREMENTS: N/A for prose; examples show metadata-only log lines.
  - Files: `docs/godot-observer.md`, `docs/research-causal-debugger.md` (and index links only if required)
  - Depends on: Task 5

<!-- Commit checkpoint: tasks 5-6 -->

## Acceptance criteria

- Selecting an event such as “Alice attacked Bob” and pressing **Why?** loads the existing server causal-trace projection (no local causal assembly).
- Default inspector shows the compact strip: Observed, Remembered, Believed, Felt, Wanted, Expected, Decided, Acted, with locked status rollup.
- Expansion reveals the full structured artifact labels in server chain order (Emotion before Goals), still from server `stage_code`s only.
- Seek and Provenance are separate affordances; Provenance uses existing lineage GET with `owner_id` from `address.agent_id`; researcher can return to the original decision without losing the primary payload on Seek.
- Visual chrome distinguishes objective event, observation, memory, belief, imagination, counterfactual, and analytical inference — subjective/imaginative rows do not look like objective reality.
- UI stays compact; no Research UI graphs/statistical dashboards are added.
- No new capability flag; V1 regression gate remains green flags-off and tracing-off; no private CoT/prompt/text bodies exposed.
