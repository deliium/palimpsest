# Implementation Plan: Research Causal Debugger + Observer Timeline Integration

Branch: none (`git.create_branches=false`; current branch `main`)
Created: 2026-10-03
Improved: 2026-10-03 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete milestone; this plan is a read-only research observability surface over already-stored cognition traces and subjective provenance — it does not claim `multi_hop_testimony_tracking` or any new capability flag.

## Downstream V2 plan contract
This plan must satisfy `docs/architecture.md` Downstream V2 plan contract:

1. V1 invariants intact (WorldEngine authority, Observation trust, subjective ≠ objective fold, no CoT/payload logging, append-only history).
2. No new `V2CapabilityFlags` slot. Debugger is observational only; reserved/unowned flags stay default-off / fail-closed.
3. V1 regression gate stays green under flags-off **and** tracing-off. Debugger routes must not be added to the V1 gate; tracing-off runs return explicit unavailable statuses without inventing stages.
4. Prefer no runner-config bump. If durable counterfactual/prediction refs need a cognition-trace schema bump, use accepted-set + exact key-set discipline (`cognition-trace-v1` → additive `cognition-trace-v2` only when proven necessary). Default event write / observer-protocol stay unchanged.
5. No scripted emergence.
6. No LLM→world shortcuts; debugger never translates LLM text into commands.
7. Experiments stay reproducible; opening debugger, seeking, or deep-linking must not change seeds, event ids, or `exact_trajectory_hash`.
8. Cognition traces remain outside `EvidenceManifest` / objective high-water. Debugger is GET-only and incapable of mutating historical simulation.

## Overview

Researchers need to answer **"Why did this selected graphical event happen?"** for cases such as:

```text
tick 1832
event 17          # UI label = intra-tick sequence (not opaque event_id)
Alice attacked Bob
```

without depending on Godot internals or private model chain-of-thought.

V2 already stores optional structured cognition-trace invocations (`cognition-trace-v1`, Alembic `0013`) and subjective provenance (memory lineage, belief evidence, communication transmission meta, goals, ToM, narrative ledgers). Counterfactual audits are harvested into runner/experiment result documents; causal hypotheses are not first-class persistence rows today. HTTP read routes for traces were explicitly deferred by `.ai-factory/plans/v2-cognitive-execution-trace.md`. The observer timeline already seeks by `(tick, sequence)` / `event_id` and can phrase events like `Alice attacked Bob`.

This plan adds a **read-only research causal debugger** that:

1. Resolves a stable event address → actor cognition invocation → structured causal chain
2. Exposes drill-down lineage navigators over previously stored artifacts
3. Provides Observer / Research UI GET APIs (no reasoning in Godot)
4. Defines bidirectional deep-link / state parameters between the graphical observer and the debugger

### Target researcher-facing chain

```text
Observation
→ relevant memories
→ reconstruction
→ beliefs
→ emotional state
→ goals
→ Theory of Mind
→ imagined futures
→ counterfactuals (when relevant / available)
→ selected intention
→ action
```

Map onto existing `CognitionTraceStageKind` where possible (`retrieved_memories`, `reconstructed_memories`, `situation_model` may appear as supporting nodes; budget_summary is optional/collapsed). Counterfactuals are a debugger-view node assembled only from locked read sources (below) — status `unavailable` otherwise. Never invent free-text rationales.

## Design Decisions (locked)

### Package and trust boundaries

1. **Assembler lives in `simulation`.** Add `simulation.causal_debugger` (public facade re-exports) owning frozen address/chain DTOs, resolution rules, and a `CausalDebuggerService` protocol. It may use `CognitionTraceRepository` + injected read ports for events and lineage enrichment. It must not import `api`, `observer` Godot client paths, `WorldEngine`, or live cognition inputs. Persistence implements enrichment ports; API wires them.
2. **`api` must not import `analysis`.** Keep join/assembly on the simulation + persistence path (same pattern as inspection / subjective_debug). Analysis may later consume the same simulation DTOs offline; do not put required debugger HTTP behind analysis imports.
3. **`observer` stays presentation-facing.** Thin deep-link / focus contracts and optional observer-route helpers for address resolution may live under `observer` or `api` schemas, but **no causal assembly logic in GDScript**. Godot only: select event → GET → render payload → emit seek/focus from returned focus handles.
4. **Capability gate (single):** All `/v1/simulations/{run_id}/debugger/*` routes require `subjective_debug`. No separate `objective_inspection` stub surface in this plan. Credentials stay header / WS subprotocol only — never query-string tokens (deep-link params are run/tick/event/agent only).
5. **HTTP status matrix:** `403` when capability missing; `404` when the addressed event is not found; `200` with `availability=unavailable` (and stable reason codes) when the event exists but cognition traces / optional lineage sources are missing. Never invent stage content.
6. **Read-only:** Debugger HTTP surface is GET-only. No POST/PATCH/DELETE that mutates runs, events, traces, memories, beliefs, or checkpoints. Seeking is a client cursor change over already-committed history.

### Stable addressing

Every debugger entry is addressable by:

| Field | Role |
| --- | --- |
| `run_id` | Simulation run |
| `tick` | Logical tick of the selected occurrence |
| `event_id` | Opaque committed event id (**preferred** stable key) |
| `sequence` | Intra-tick sequence; UI phrase “event N” means this field |
| `agent_id` | Acting / owning agent (usually `actor_id`) |

**Resolution rule (deterministic):**

1. Load committed event via `DebuggerEventLookupPort` by `(run_id, event_id)` or `(run_id, tick, sequence)`.
2. Derive `agent_id` from `actor_id` when present; if absent (e.g. some environmental events), return `causal_trace_not_applicable` — do not guess.
3. Map observer semantic type / world event details → expected `command_kind` via the closed Task 1b table (e.g. `AGENT_ATTACKED` → `"attack"`). Secondary consequence events (e.g. `AGENT_DIED` after a lethal hit): if `actor_id` is absent / is the victim only, `not_applicable`; if an attacking `actor_id` is present on that occurrence, resolve that actor’s same-tick invocation.
4. List cognition-trace invocations for `(run_id, agent_id, tick)`.
5. Prefer the invocation whose `command_kind` matches the mapped kind when unique; if multiple remain, pick lowest `invocation_id` lexicographically and set `ambiguity=true` + reason code `multiple_invocations`.
6. If tracing was off / null sink / empty: return structured `availability=unavailable` with reason `cognition_trace_missing` — never synthesize stage content.

Address equality must be stable across process restarts (opaque ids + tick/sequence), independent of Godot node paths.

### Counterfactual & prediction read sources (no new authoritative tables)

Priority order for optional nodes / prediction lineage:

1. Structured id_refs / counts / decision_metadata already on the selected `CognitionTraceInvocation` stages
2. Else, if an experiment/runner result document for the run is available and carries harvested `counterfactual_audits` (or equivalent) for that owner/tick — use closed summary fields only
3. Else `status=unavailable` with an explicit reason code

Do **not** add Alembic tables or `cognition-trace-v2` in this plan solely to durably store full counterfactual audits or hypothesis snapshots. Richer historical prediction/counterfactual lineage is out of scope until a later plan.

### Causal chain assembly

- Project the researcher chain from the stored `CognitionTraceInvocation` stage summaries + closed ID refs / counts / bands / reason codes only.
- Simulation DTOs use `DebuggerFocusHandle` (not `ObserverFocusHandle`) to avoid colliding with the `observer` package. Wire/JSON field name remains `observer_focus` for Godot/API consumers.
- **Forbidden on all debugger DTOs and logs:** `rationale`, `chain_of_thought`, `prompt`, `raw_response`, observation/memory/belief/utterance text bodies, credentials, endpoints. Mirror `ComponentBoundaryRecord` / cognition-trace forbid lists.
- Counterfactuals / prediction provenance follow the locked read-source order above.
- Situation model / budget summary may appear as secondary nodes; they must not replace the researcher chain order above.

### Lineage navigators (drill-down)

Separate GET resources (or nested expandable nodes with lazy fetch keys) for:

| Navigator | Primary sources (scoped) |
| --- | --- |
| Belief evidence | Owner-scoped belief evidence already used by inspection subjective routes |
| Memory derivation | `MemoryLineage`, reconstruction ids, source_memory_ids |
| Communication lineage | `CommunicatedTransmissionMeta`, cited/declared lineage, delivery event ids |
| Narrative lineage | owner `NarrativeLedger` variant parents / competing variants (same class of source as observer narrative-hops) |
| Goal ancestry | hierarchical goals via `parent_goal_id` / `GoalBoard` projections available on subjective/checkpoint paths already used by inspection — not a new goal store |
| Prediction provenance | hypothesis ids from cognition-trace refs / decision_metadata first; else unavailable per read-source lock |

Each lineage node that refers to a committed world occurrence MUST carry a **focus handle** (`DebuggerFocusHandle` → wire `observer_focus`): `{run_id, tick, sequence, event_id}` (nullable fields only when truly unknown) so the UI can seek/focus without Godot inventing correlation.

### Observer integration API

Provide read-only APIs so Godot observer or Research UI can:

```text
select event
→ request causal trace
→ display/open debugger
```

Routes (all `subjective_debug`):

- `GET /v1/simulations/{run_id}/debugger/events/{event_id}/causal-trace`
- `GET /v1/simulations/{run_id}/debugger/causal-trace?tick=&sequence=` (alternate address)
- `GET /v1/simulations/{run_id}/debugger/agents/{agent_id}/invocations?tick=`
- `GET /v1/simulations/{run_id}/debugger/lineage/{kind}/{id}` (closed `kind` enum)

Wire through API composition using persistence cognition-trace repository + enrichment ports. Do not put assembly in Godot. Do not require a full separate Research UI app in this plan — a Godot debugger panel that renders the server payload is enough for observer integration; a headless/OpenAPI consumer remains first-class.

### Timeline interoperability (bidirectional)

| Direction | Mechanism |
| --- | --- |
| Godot event → debugger | Selected `(run_id, tick, sequence, event_id, agent_id)` → GET causal-trace → open panel |
| Debugger evidence → Godot | Click node with `observer_focus` → client `seek_event(tick, sequence)` / `focus_event_ids` |

### Deep-link / state parameters

Define a stable, credential-free state record (URL query for web export and/or in-client state):

| Param | Required | Notes |
| --- | --- | --- |
| `run_id` | yes | Existing web query already applies run_id |
| `tick` | yes for event focus | Non-negative int |
| `event_id` | preferred | Opaque id |
| `sequence` | with tick when known | Intra-tick sequence; UI “event N” |
| `agent_id` | optional | Preselect perspective / chain owner |
| `debugger` | optional | `1` / `causal` opens debugger panel after seek |

Reject credential-like query keys (`token`, `api_key`, …) via existing `reject_query_string_secrets`. Document canonical encoding in `docs/godot-observer.md` / debugger docs.

### Godot client scope

- Add a read-only debugger panel/view under `clients/godot-observer/` that renders server chain + lineage summaries.
- On event log / timeline selection: optional “Explain” / open-debugger action that GETs the causal-trace route with the session token header (existing auth path).
- On capability `403` / missing `subjective_debug`: use the same `overlay_unavailable` pattern as narrative/relationship overlays — never render an empty chain as “no cognition”.
- On lineage node activation: emit existing seek/focus signals from returned focus handles.
- Apply deep-link params on web boot (extend `apply_web_query`).
- **No** local reconstruction of memories/beliefs/ToM; **no** utterance text; **no** mutating HTTP.

### Non-goals

- Exposing private model chain-of-thought, prompts, or raw provider text
- Mutating, reseeding, or inverse-replaying history from the debugger
- Putting causal assembly or lineage logic in Godot
- Claiming `multi_hop_testimony_tracking` or enabling reserved flags
- Folding traces into `EvidenceManifest` / stream outbox
- Shipping a separate full Research SPA (server API + Godot panel is sufficient)
- Pausing the simulation from the debugger
- New Alembic tables / `cognition-trace-v2` solely to persist full counterfactual audits or hypothesis snapshots (later plan if needed)
- Separate `objective_inspection` debugger stub routes

## Commit Plan
- **Commit 1** (after tasks 1–3): `feat(simulation): causal debugger addresses, mapping, and chain assembly`
- **Commit 2** (after tasks 4–6): `feat(api,persistence): debugger read APIs and lineage ports`
- **Commit 3** (after tasks 7–9): `feat(godot,observer): debugger panel and bidirectional deep links`
- **Commit 4** (after tasks 10–11): `test(docs): research debugger gates and documentation`

## Tasks

### Phase 1: Addresses, mapping, lookup, assembly

- [x] Task 1: Define stable debugger address and causal-chain DTOs
  - Deliverable: Under `src/simulation/causal_debugger.py` (re-export from `simulation` facade), add frozen types:
    - `DebuggerEventAddress(run_id, tick, event_id | None, sequence | None, agent_id | None)` — document that UI “event N” = `sequence`; prefer opaque `event_id` when known
    - `DebuggerFocusHandle(run_id, tick, sequence | None, event_id | None)` (simulation name; wire field `observer_focus`)
    - `CausalTraceNode` (stage code, status, closed counts/bands/reason codes, id refs, optional focus handles)
    - `CausalTrace` (address, invocation_id, availability, ambiguity flag, ordered nodes for the researcher chain)
    - Closed enums for availability / lineage kind; explicit forbid-attribute validation mirroring cognition-trace (no CoT/prompt/raw fields)
  - Document mapping from `CognitionTraceStageKind` → researcher chain labels (including optional counterfactual node).
  - LOGGING REQUIREMENTS: DEBUG construction with run_id/tick/event_id/agent_id/stage codes/counts only; ERROR on forbidden fields with stable reason codes; never log payloads/text.
  - Files: `src/simulation/causal_debugger.py`, `src/simulation/__init__.py`, `tests/unit/test_causal_debugger_models.py`
  - Dependencies: None

- [x] Task 1b: Lock closed semantic/event → `command_kind` mapping and multi-event rules
  - Deliverable: Closed, tested mapping from observer semantic types / world event detail types to cognition-trace `command_kind` strings as actually stored (`type(command).__name__.lower()` / `agent_command_tag`, e.g. `AGENT_ATTACKED` / `Attacked` → `"attack"`). Document secondary-effect rules (`AGENT_DIED` without attacking actor → `not_applicable`; lethal attack sequence still explains via the Attacked occurrence’s actor). Export a pure helper used by the resolver — no Godot logic.
  - LOGGING REQUIREMENTS: DEBUG mapped semantic→command_kind; WARN unknown semantic with reason `unmapped_semantic_type`; never log payloads.
  - Files: `src/simulation/causal_debugger.py` (or `debugger_command_map.py`), `tests/unit/test_causal_debugger_command_map.py`
  - Depends on: Task 1

- [x] Task 1c: Lock counterfactual / prediction read sources (no new tables)
  - Deliverable: Written lock + small typed accessors/ports for the priority order in Design Decisions (trace refs → optional experiment/result harvest → unavailable). Explicit reason codes for each miss path. Confirm this plan does **not** add Alembic / `cognition-trace-v2` for full audit/hypothesis blobs.
  - LOGGING REQUIREMENTS: DEBUG source chosen (trace|result|none) with owner/tick/counts only; WARN harvest incomplete/legacy; never log scenario text.
  - Files: `src/simulation/causal_debugger.py` (docs + port stubs), unit tests for source selection
  - Depends on: Task 1

- [x] Task 1d: Define `DebuggerEventLookupPort` (by `event_id` and by `(tick, sequence)`)
  - Deliverable: Protocol + in-memory fake returning committed event identity fields needed for resolve (`event_id`, `tick`, `sequence`, `actor_id`, semantic/detail kind). Persistence/API implementation may reuse event store / replay keyset readers but must not call Godot or import `observer` client paths. Prefer indexed/direct lookup over observer_service’s full keyset scan when wiring adapters (Task 5); if only keyset exists initially, encapsulate it behind the port and note a follow-up index only if proven necessary (justify like `0013`).
  - LOGGING REQUIREMENTS: DEBUG lookup keys; WARN not-found; ERROR invalid address combinations (`incomplete_event_cursor`); never log event payloads beyond ids/kinds.
  - Files: `src/simulation/causal_debugger.py`, `tests/fakes/`, `tests/unit/test_causal_debugger_event_lookup.py`
  - Depends on: Task 1

- [x] Task 2: Implement event→invocation resolution
  - Deliverable: Pure/async resolver that uses `DebuggerEventLookupPort` + Task 1b mapping + `CognitionTraceRepository.list_invocations` and returns the selected invocation key or typed unavailable/not-applicable per locked rules (actor required; command_kind match; lexicographic `invocation_id` tie-break; `ambiguity` flag).
  - Unit tests: Alice attacked Bob (`tick` + `sequence` + actor + `"attack"`); missing trace; multi-invocation ambiguity; environmental event without actor; Died-without-actor → not_applicable.
  - LOGGING REQUIREMENTS: INFO on successful resolve (ids/counts only); WARN on ambiguity / unavailable with reason codes; DEBUG candidate counts; never log observation or utterance bodies.
  - Files: `src/simulation/causal_debugger.py`, `tests/unit/test_causal_debugger_resolve.py`
  - Depends on: Tasks 1, 1b, 1d

- [x] Task 3: Assemble researcher causal chain from stored cognition-trace stages
  - Deliverable: `assemble_causal_trace(invocation, *, counterfactual_source=…)` projects ordered researcher nodes from stage summaries + optional counterfactual structured refs **only via Task 1c sources**. Missing optional stages → `unavailable` with reason codes (not omissions that look like success). Reject embedding full Observation / WorldEvent / prompts. Include action node from `planned_action` / `command_kind` only (type codes, not free text). Attach `DebuggerFocusHandle` on nodes when occurrence ids are known.
  - LOGGING REQUIREMENTS: DEBUG `causal_trace_assembled` with invocation_id, agent_id, tick, node_count, unavailable_count; ERROR schema/forbid violations; metadata-only.
  - Files: `src/simulation/causal_debugger.py`, `tests/unit/test_causal_debugger_assemble.py`
  - Depends on: Tasks 1, 1c

<!-- Commit checkpoint: tasks 1-3 (incl. 1b–1d) -->

### Phase 2: Lineage ports, persistence, HTTP API

- [ ] Task 4: Define lineage enrichment ports and closed lineage DTOs
  - Deliverable: Protocols for belief evidence, memory derivation, communication lineage, narrative lineage, goal ancestry, and prediction provenance. Each response includes stable ids + optional `DebuggerFocusHandle`s for committed events. Ports accept `(run_id, owner/agent_id, subject_id)` and return structured summaries only. Prediction port must honor Task 1c (trace refs first → unavailable).
  - In-memory fakes for unit tests; no SQL in this task.
  - LOGGING REQUIREMENTS: DEBUG port entry/exit with kind/id/counts; WARN incomplete/legacy provenance; ERROR invalid kind; never log proposition/narrative text.
  - Files: `src/simulation/causal_debugger.py` (or `src/simulation/debugger_lineage.py`), fakes under `tests/fakes/`, unit tests
  - Depends on: Tasks 1, 1c

- [ ] Task 5: Persistence adapters for event lookup, lineage enrichment, and cognition-trace reads
  - Deliverable: SQLAlchemy (and in-memory where needed) implementations scoped to:
    - existing cognition-trace repository
    - `DebuggerEventLookupPort` over the objective event store / replay readers
    - owner-scoped memory / belief / relationship / narrative ledgers already used by inspection and observer subjective routes
    - counterfactual/prediction only via Task 1c sources (no new hypothesis tables)
  - Prefer no Alembic revision; only add a migration if an indexed query column is proven necessary for debugger event lookup (justify like `0013`). Wire factory helpers beside existing `create_cognition_trace_repository`.
  - LOGGING REQUIREMENTS: DEBUG query keysets (run_id, tick, ids, page sizes); WARN not-found; ERROR adapter failures with safe codes; never log DSN/payloads.
  - Files: `src/persistence/*` (new or extend existing), `src/api/persistence_services.py` / durable wiring, architecture import-linter tests if new edges appear
  - Depends on: Tasks 1c, 1d, 4

- [ ] Task 6: FastAPI read-only debugger routes
  - Deliverable: Versioned GET routes under `/v1/simulations/{run_id}/debugger/…` for causal-trace by `event_id` and by `tick`+`sequence`, invocation listing, and lineage drill-downs. **All** routes require `subjective_debug` (no objective stub routes). Enforce status matrix: `403` / `404` / `200`+`availability=unavailable`. Pydantic response models with exact key sets; wire focus field name `observer_focus`; OpenAPI descriptions state observational / non-mutating. Compose `CausalDebuggerService` in API — no `analysis` import.
  - LOGGING REQUIREMENTS: INFO `route_debugger_*` with route_template, status, run_id, duration_ms, counts; DEBUG address fields; never log secrets or subjective text bodies.
  - Files: `src/api/routes/debugger.py` (new), schemas, router registration, `tests/unit` / API contract tests
  - Depends on: Tasks 2, 3, 5

<!-- Commit checkpoint: tasks 4-6 -->

### Phase 3: Observer deep links + Godot panel

- [ ] Task 7: Define bidirectional deep-link / state parameter contract
  - Deliverable: Document and implement canonical state params (`run_id`, `tick`, `event_id`/`sequence`, `agent_id`, `debugger`) for web query + in-client state. Clarify UI “event N” = `sequence`. Server responses for causal nodes include `observer_focus` handles (`DebuggerFocusHandle` serialized). Add a small pure helper (Python) to parse/validate debugger state without accepting credentials in query strings. Extend Godot `apply_web_query` to seek + optionally open debugger after connect.
  - LOGGING REQUIREMENTS: DEBUG parse/apply with param keys and reason codes; WARN invalid combinations (`incomplete_event_cursor`, etc.); never log tokens.
  - Files: `src/observer/` or `src/api/` helper + tests; `clients/godot-observer/scripts/**`; `docs/godot-observer.md` (final docs polish in Task 11)
  - Depends on: Task 1

- [ ] Task 8: Godot — select event → request causal trace → open debugger panel
  - Deliverable: UI affordance on event log/timeline selection; HTTP GET via existing session client + capability token header; render ordered chain from server JSON (stage labels, statuses, counts, id refs). Show clear empty/unavailable states when tracing was off. On HTTP `403` / missing `subjective_debug`, use the same `overlay_unavailable` pattern as narrative/relationship overlays — do not present auth failure as an empty causal chain. No local causal reasoning.
  - LOGGING REQUIREMENTS: GDScript `[observer.debugger]` INFO open/close; DEBUG request address + HTTP status + node_count; WARN capability/unavailable reason codes; no utterance/memory text.
  - Files: `clients/godot-observer/scripts/**`, scenes as needed, `clients/godot-observer/tests/*.gd`
  - Depends on: Tasks 6, 7

- [ ] Task 9: Godot — debugger evidence → seek/focus on timeline
  - Deliverable: Activating a node that carries `observer_focus` emits existing `seek_event` / narrative focus paths so the timeline/log highlights the evidence occurrence. Round-trip test: event → debugger → evidence focus → same tick/sequence selected (and `event_id` focus when provided). Verify UI wiring end-to-end before marking complete.
  - LOGGING REQUIREMENTS: DEBUG focus handles; INFO seek from debugger; no payload bodies.
  - Files: `clients/godot-observer/scripts/**`, GDScript tests
  - Depends on: Task 8

<!-- Commit checkpoint: tasks 7-9 -->

### Phase 4: Hardening, docs, regression

- [ ] Task 10: Tests for safety, determinism, and V1 gates
  - Deliverable:
    - Forbid-attribute / no-CoT tests on debugger DTOs and JSON responses
    - Deterministic resolve/assemble property or table tests (incl. command map + Died/Attacked cases)
    - API auth tests: without `subjective_debug` → `403`; with capability → chain; missing event → `404`; tracing-off → `200` + unavailable
    - Import-linter / architecture: `api` ↛ `analysis`; debugger assembly ↛ `WorldEngine` / private `world._*`; Godot not imported from `src/`
    - Confirm `tests/unit/test_v1_regression_gate.py` still green flags-off and tracing-off; debugger not added to that gate
    - Confirm GET-only surface (no mutating debugger routes)
    - Run `ruff check` on the full changed-file set including `__init__.py` exports
  - LOGGING REQUIREMENTS: Tests assert log metadata allowlists where applicable; failure messages use reason codes.
  - Files: `tests/unit/`, `tests/architecture/` as needed
  - Depends on: Tasks 1–9

- [ ] Task 11: Documentation checkpoint (`/aif-docs`)
  - Deliverable: Update contributor docs:
    - New or extended page for research causal debugger (addressing, sequence vs event_id, command map, chain mapping, lineage kinds, Task 1c sources, auth status matrix, non-mutation)
    - `docs/godot-observer.md` — deep-link params, select→explain flow, 403/unavailable handling, focus return path
    - `docs/architecture.md` — update cognition-trace seam note from “ports only (no HTTP yet)” to debugger HTTP + observational constraint
    - `docs/observer.md` / API docs cross-links as needed
    - README landing link if the docs index requires it
  - LOGGING REQUIREMENTS: N/A for prose; examples must show metadata-only log lines.
  - Files: `docs/**`, `.ai-factory/DESCRIPTION.md` only if feature list needs a one-line debugger mention
  - Depends on: Task 10

<!-- Commit checkpoint: tasks 10-11 -->

## Acceptance criteria

- Given a committed `AGENT_ATTACKED` at a known `(run_id, tick, sequence)` with cognition tracing enabled for the actor, `GET …/debugger/…/causal-trace` (with `subjective_debug`) returns a structured chain covering observation → memories → reconstruction → beliefs → emotion → goals → ToM → imagined futures → counterfactuals (or unavailable per Task 1c) → intention → action, using stored trace/provenance only.
- UI “event 17” is treated as `sequence`; stable addresses prefer opaque `event_id` and still carry `(tick, sequence)` when known.
- Every node and lineage entry is addressable via `run_id` + tick/event/agent identifiers as applicable.
- Godot can select that event, open the debugger from the API payload, handle `403` like other subjective overlays, and seek back from an `observer_focus` handle — without embedding reasoning logic in GDScript.
- Deep links encode `run`, `tick`, `event`/`sequence`, `agent` (plus optional debugger open flag) without credentials in the query string.
- Debugger cannot mutate historical simulation; V1 regression gate remains green with flags-off and tracing-off; no private CoT is exposed; no new authoritative tables for counterfactual/hypothesis blobs in this plan.
