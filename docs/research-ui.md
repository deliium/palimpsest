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
