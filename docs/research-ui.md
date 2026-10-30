# Research UI

[← Research API](research-api.md) · [Back to README](../README.md) · [Godot observer →](godot-observer.md)

Researcher-oriented **V2 web UI** (Svelte + Vite + TypeScript) that answers *why did it happen, and what patterns emerged?* It complements the Godot World Observer, which answers *what happened in the graphical world?*

The SPA lives under `clients/research-ui/` (not a Python package). The API serves built `dist/` at **`/research/`** when `PALIMPSEST_RESEARCH_WEB_ROOT` points at a directory containing `index.html`. Mount order: `/research/` before the Godot catch-all `/`.

## Responsibility split

| Surface | Owns | Must not own |
| --- | --- | --- |
| Godot Observer (`/`) | Spatial world, timeline seek, compact Why? | Matrices, statistical dashboards, multi-graph chrome |
| Research UI (`/research/`) | Run list, matrices, graphs, ledgers, metrics, fork compare, traces, deep links | Authoritative world rendering, tick mutation, inventing emergence |

## Epistemic chrome

Every panel/node/metric chip carries exactly one presentation class:

| Class | Meaning |
| --- | --- |
| `objective_world` | Committed world / journal truth |
| `agent_observation` | Agent-visible projection |
| `agent_memory` | Owner episodic / reconstructed memory |
| `agent_belief` | Beliefs, self-model, goals, emotion, ToM |
| `agent_imagination` | Imagined futures |
| `counterfactual` | Agent CF **or** research fork (labeled which) |
| `research_inference` | Metrics, phenomenon panels, matrix stats, inferred groups/norms |

**Inferred groups, norms, conventions, and community structure are analytical results** (`research_inference` / “Analytical result”) — never unlabeled world facts on the objective timeline.

## Navigation

```text
/research/                      → inspect-scoped run list
/research/runs/:runId           → overview | graphs | agent | analytics | traces | compare
/research/matrix                → experiment-matrix-v1 overview (FS root)
/research/matrix/:matrixId      → cells + aggregate/summary keys
```

Deep-link query keys (credential-free): `run_id`, `tick`, `event_id`, `sequence`, `agent_id`, `view`. Secret-like keys are rejected. Tokens stay in headers / sessionStorage capability slots only.

## Auth

Four in-memory / sessionStorage slots — control, inspection, agent_visible, debug — injected as `x-palimpsest-token` matching the route capability. Open-local when secrets are unset.

## Data sources (high level)

- Run discovery: `GET /v1/research/runs` (`objective_inspection`) — not control `GET /v1/simulations`
- Subjective projections: goals, emotional-state, self-model **projection**, ToM, group/norms/conventions/narratives (`subjective_debug`)
- Graph summaries: `…/memories/summary`, `…/beliefs/summary` (metadata-safe ids only). Count-only `SubjectivePageOut` pages remain unchanged for older clients
- Relationships: observer relationship summaries; social delivery edges from Talked/Asked/Told observer events
- Analytics: metric catalog/documents + ledger summaries (visually separated)
- Traces: existing debugger GETs
- Matrix FS: `GET /v1/research/matrices…` under `PALIMPSEST_RESEARCH_MATRIX_ROOT` (allowlisted files; no `analysis` import)
- Fork compare: `POST /v1/simulations/branches/compare` (research-fork `counterfactual` chrome)

## Godot interoperability

- Research → Godot: `/?run_id&tick&event_id&agent_id` (+ `debugger=1` for Why?)
- Godot → Research: `ResearchUiLink.open` via `JavaScriptBridge` / `OS.shell_open` (Why? panel **Research UI** button)
- Optional same-origin iframe embed on overview; bootstrap failure → new tab

## Local build

```bash
cd clients/research-ui
pnpm install
pnpm test && pnpm build
export PALIMPSEST_RESEARCH_WEB_ROOT="$PWD/dist"
```

See [Development](development.md) and `compose.dev.yaml` for optional compose env passthrough.

## V2 benchmark artifacts

Allowlisted matrix trees under `PALIMPSEST_RESEARCH_MATRIX_ROOT` may include the example `v2-benchmark-suite` manifest plus runtime `aggregate.json` / `metric-summary.json` sidecars. See [V2 benchmark suite](v2-benchmark-suite.md). Unit acceptance: `tests/unit/test_benchmark_research_ui_artifacts.py`.

## V3 extension strategy

Keep `/research/` mount and `/v1` data origin. Prefer additive inspect views, optional query params, and existing epistemic chrome (`agent_belief` vs `research_inference`). Future lineage/settlement/institution/long-horizon compare surfaces consume existing inspection/matrix/branch APIs first; new HTTP shapes only when optional fields cannot express them. Research UI must not start batches, mutate world state, or treat analytical labels as agent-visible truth. Matrix FS schemas stay v1 unless a later plan needs a versioned bump.

Historical memory metric families (`historical_memory_layers`, `historical_memory_transitions`, `historical_memory_queries`) map through `ANALYTICAL_OVERLAYS` to `research_inference` only. AnalyticsPanel may surface layer histograms and query answers from the metric catalog; GraphsPanel provenance chrome for Assmann layers remains deferred. Never add Assmann layer labels to subjective ledger endpoints (`cultural_narratives`, norms, conventions, group formation).

## Historical paging controls

Research UI history views keep one buffered page suffix and drain it before
advancing a server cursor. Local item caps return an explicit `limited` state
with a continuation action; queue saturation is typed and bounded. Marker
discovery is explicit: the first boundary page is followed by a visible
"Load more generations" continuation, and incomplete discovery is labelled.
Refreshing markers re-fetches the run head before advancing high water. Lineage
snapshot discovery resolves the exact requested boundary within a bounded scan;
when the budget ends it shows `scan_limited` plus "Continue publication scan"
rather than substituting the first snapshot. Scope/credential changes abort
in-flight work, reject stale responses, and clear private cached rows. There is
no localStorage/IndexedDB historical cache. See
[Long-horizon scalability](long-horizon-scalability.md).

## See also

- [Research API](research-api.md)
- [Godot observer](godot-observer.md)
- [Research causal debugger](research-causal-debugger.md)
- [V2 benchmark suite](v2-benchmark-suite.md)

## Societies view

The run-scoped **Societies** tab reads the existing family-agnostic metric
catalog and document endpoints (`GET /v1/simulations/{run_id}/metrics` and
`.../metrics/{metric_set_id}/{metric_family}`). It renders
`society_emergence`, `society_divergence`, and `society_isolation` documents
under `research_inference` chrome with the `analytical_inference` epistemic
class. Candidate communities and isolation findings are never presented as
objective facts or agent-visible labels; no Godot/observer protocol change is
required.


## Contact view

The run-scoped `contact` view lists `society_contact`, `contact_cultural_change`,
`contact_hybrid_practice`, `contact_knowledge_transfer`,
`contact_lexical_borrowing`, and `contact_reputation_transfer` from the generic
metric endpoints under `research_inference` chrome. It never presents analytical
results as agent-visible facts and adds no backend route or content payload.

## Symbolic-language view

A researcher-only `SymbolicLanguagePanel` may read
`GET /v1/simulations/{run_id}/observer/agents/{agent_id}/symbolic-language`
under the existing `research_inference` / `analytical_inference` chrome. It
renders digests, bands, counts, and operator mix only; it never displays raw
tokens, message bodies, or prompts, and it does not claim semantic correctness
or convergence.

## Analytical institution panel

`InstitutionsPanel.svelte` reads `institution_emergence` and
`institutional_persistence` through the existing family-agnostic metric
endpoints. Both families map through `ANALYTICAL_OVERLAYS` to
`research_inference` chrome. No backend API, observer protocol, Godot semantic
type, or subjective endpoint changes. Candidates and persistence
classifications are never presented as agent-visible facts.

## Generational research surfaces (V3-42)

The run shell now groups Population, Lineage, Culture, Space, Institutions and
Economy without removing legacy tabs/routes. Every requested surface is
reachable with a populated or explicitly unavailable state.

| Surface | UI home | Source / evidence |
| --- | --- | --- |
| Population timeline | Population | Objective demographics at sampled finalized boundaries |
| Demographic charts | Population | Exact whole-population totals; stage/generation rows |
| Genealogy | Lineage (genealogy) | Objective lineage snapshots/traverse |
| Cohort comparison | Cohorts | Objective census; composite `(run, generation, entry tick, cohort id)` |
| Teacher/student networks | Teaching | Mentorship subjective/analytical participants + returned edges |
| Knowledge genealogy | Lineage (knowledge) | Owner-scoped/analytical knowledge lineage |
| Technology lineage | Technology · Lineage | Technology/knowledge lineage |
| Technology diffusion | Technology · Diffusion | Civilization technology overlays + objective anchors |
| Cultural trait timelines | Culture | Paged cultural evidence traits |
| Vocabulary evolution | Language · Vocabulary | Captured `vocabulary` inventory |
| Semantic drift | Language · Semantics | Retained owner checkpoint sense history |
| Migration flows | Migration | Civilization migration overlays + objective map rows |
| Society comparison | Societies | Candidate community lanes and stored society metrics |
| Narrative lineage | Narratives | Narrative metadata + narrative lineage family |
| Institution timeline | Institutions · Timeline | Concept/office/episode lanes |
| Office succession | Institutions · Office succession | Subjective `office_succession` lineage |
| Institution lineage | Institutions · Lineage | Analytical `institution` lineage |
| Economic exchange networks | Economy | Completed trade overlay hubs (no prices/balances) |
| Collective project history | Projects | Objective project state + retained receipts |
| Generation and tick navigation | Shared navigator | Markers discovered at high-water H; view tick T |
| Seven Godot focus dimensions | Share/open links | Run, tick, agent, location, institution, narrative, technology |
| Objective/subjective/analytical distinctions | Every series/node/edge/row | Per-item badges, owner and window text |

### Marker discovery H versus view tick T

Generation markers are discovered at the finalized high-water `H` from
`GET /observer/run`; viewing boundary `T` never lowers `H`. Selecting a marker
keeps `H` and seeks its server-provided `seek_tick`. Only an explicit Refresh
may advance `H`. A generation-only URL is resolved through actual admission
markers; an explicit tick takes precedence and a conflicting generation shows
`generation_tick_mismatch` rather than rewriting time.

### Cohorts, sampling and provenance

- Cohort identity always includes generation, entry tick and cohort ID. A reused
  ID across entries/generations is not merged; ID-only legacy selection resolves
  only when exactly one loaded row matches.
- Census `living / admitted` is descriptive; it is not Kaplan–Meier survival or a
  causal effect. Zero denominators show `—`.
- Full-history population sampling is explicit, bounded to 32 boundaries per
  load, and discloses omitted boundaries. Gaps are unknown, never zero, and
  sparse samples do not imply birth/death rates.
- Graphs use server budgets unless smaller local caps apply (500 nodes / 1500
  edges). Charts always include an accessible data table and keyboard-selectable
  points.
- Culture/vocabulary require an explicit matrix and cell; the app never scans all
  matrices to guess a run association. `runtime_bound` and `legacy_unverified`
  artifact binding remain visible and are independent of PRESENT/PARTIAL rows.
- Retained semantic history is as-of a checkpoint with `retained_only=true` and
  an unknown prefix. Current labels/symbolic/translation cards are current
  checkpoint metadata, not restored history.
- Capture-off, lifecycle-disabled, debug-denied, missing checkpoint and complete
  empty evidence have distinct notices. No client action starts capture, writes
  artifacts, or mutates the world.

### Deep links and embeds

Credential-free selection keys include the original run/tick/event/agent/view
keys plus `generation_index`, composite cohort keys, scope/identity owner,
evidence class, entity source, native kind, lineage family/node/publication,
civilization row/publication, and location/institution/narrative/technology IDs.
Credentials never enter URLs. The Godot embed is same-origin and isolated; its
explicit new-tab anchor is the fallback when bootstrap fails.

## Organizations panel

Read-only summary, candidate table, candidate detail, and lineage from the four
`/v1/simulations/{run_id}/organizations` routes (`subjective_debug`). Disabled and
empty states are explicit; the client performs no candidate detection, identity
minting, lineage derivation, or write call.
