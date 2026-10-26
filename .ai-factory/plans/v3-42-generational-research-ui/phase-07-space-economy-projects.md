# Phase 7: Migration, societies, exchange and project history

Plan: [index.md](index.md)  
Tasks: 17–19  
Depends on: Tasks 7–10, 14

## Objective
Render real spatial and economic evidence without promoting inferred communities into polities, or cumulative project snapshots into invented events.

## Current-Code Evidence
| Path | Symbols | Why it matters |
|---|---|---|
| `src/simulation/civilization_rows.py` | `CivilizationMigrationRow`, `CivilizationTradeRow`, `CivilizationGroupRow`, `CivilizationProjectRow` | Existing closed metadata is sufficient for requested views |
| `src/api/routes/civilization.py` | map/catalogue/overlays/markers | Objective map is replayable; captured layers are publication-pinned |
| `clients/research-ui/src/views/SocietiesPanel.svelte` | existing analytical metric cards | Extend instead of replace with another society ontology |
| `clients/research-ui/src/views/AnalyticsPanel.svelte` | economic families | Existing metric-set catalog complements, not replaces, charts |

## Files to Change
Introduce `clients/research-ui/src/components/research/TopologyMap.svelte`, `src/research/spatial.ts`, `economy.ts`, `projects.ts`, `src/views/MigrationPanel.svelte`, `EconomyPanel.svelte`, `ProjectsPanel.svelte`; modify `SocietiesPanel.svelte`; add sibling tests. Move Task14 diffusion topology into the reusable component without changing physics/layout contracts.

## Task 17: Render migration flows and society comparison
### Intent
Support temporal spatial research while separating objective movement from analytical social boundaries.
### Implementation Steps
1. `TopologyMap.svelte` takes layout-independent objective location/region/route rows, stable deterministic display positions and evidence-tagged overlays. Reuse Task14's grounding resolver: returned anchors are evidence-at-tick locations, not proof of present residence; only a matching exact-boundary objective witness can supply missing current placement. Handle regional maps without assuming Godot reference-layout IDs. Render SVG accessible node/edge lists and keyboard selection; positions never feed commands or physics.
2. MigrationPanel uses objective migration captured rows/markers at pinned windows: route/origin/destination, phase, participants, starts/arrivals/ends/waits. Provide flow map and table with time-range/route/region filters, population generation context only where known. Deduplicate repeated journey rows by journey/window/boundary semantics; do not sum repeated cumulative counts across snapshots.
3. Extend SocietiesPanel to compare selected candidate communities from `social_groups` overlays at the same captured boundary, with membership/basis/missing lanes and the existing emergence/divergence/isolation stored metrics. Side-by-side population/culture/technology data must state source and denominator; no joining different community policy versions as identical.
4. Allow at most two explicitly selected runs for society comparison via existing inspect run picker. Each has independent tick/capture/publication; require the user to align by explicit tick or generation marker and display both. Equal generation numbers do not imply equal age/time or community identity.
### Required Interfaces and Contracts
Migration is co-presence/movement, not citizenship, borders or polity membership. Group IDs are analysis scoped to run/policy/window; private owner groups stay in a separate lane. Unknown residence/trust/interaction evidence stays unknown. Map topology can remain available without captures.
### Requirement Evidence
User migration flows/society comparison; regional migration and civilization-layer trust boundaries.
### Error Handling and Logging
Missing spatial grounding yields a table/unlocated list; never position by latest state. Capture gaps shown as missing bands. Request/source/count metadata only.
### Tests
Actual migration phases, duplicate journey snapshots, no inferred border; group basis/version mismatch, partial missing lanes, two-run alignment, disabled capture, objective and subjective group overlap; keyboard map selection. Exercise real civilization map and marker fixtures.
### Acceptance Criteria
Migration map/flows and two-society comparison display actual evidence and bounded temporal alignment.
### Verification
`pnpm --dir clients/research-ui test src/research/spatial.test.ts src/views/MigrationPanel.test.ts src/views/SocietiesPanel.test.ts`.

### Grounding verification additions
Test valid/invalid source-ref ticks, multiple anchors with no unique current placement, old historical anchors, body/agent ID conversion, unsupported observer layout and topology-only regional data. No marker becomes located by current/latest coordinates when its evidence is historical.

## Task 18: Render economic exchange networks
### Intent
Visualize completed exchanges without inventing currency, price systems, debt enforcement or wealth measures.
### Implementation Steps
1. EconomyPanel loads analytical `trade` layer for a captured window; use participant refs as nodes, returned participant set as exchange relation and returned completed count/item-kind forward/reverse counts as edge detail. For more than two participants, render an exchange hub with membership edges; do not project a clique of invented bilateral trades.
2. Network and table show window, location where known, count, item kinds and evidence refs. Preserve every row identity/window. Repeated cumulative snapshots are not added as independent exchanges; single-window totals only unless disjointness is proven by returned windows and refs.
3. Add stored commitment/exchange/medium-of-exchange metric adapters to the panel. Show completed transfers as analytical summaries of objective receipts; private reservation/valuation remains subjective and is not inferred from item counts.
4. Add agent/location navigation and evidence-class legend; local graph limits from Task8 apply.
### Required Interfaces and Contracts
No price, currency, account balance, debt obligation or economic class is synthesized. Node size may represent displayed edge count only with clear unit; do not call it wealth or power.
### Requirement Evidence
User economic exchange networks; `CivilizationTradeRow` fields and architecture's commitments/valuations trust rules.
### Error Handling and Logging
No trade channel versus complete no exchange is distinct. Bounded/truncated graphs retain table continuation. Logs counts/outcomes, never item payloads or valuation strings.
### Tests
Real trade overlay fixture, zero exchanges, multiple participants, overlapping windows, repeated row, unknown location, unsupported metric units, graph budget and agent links.
### Acceptance Criteria
A functional exchange network and evidence table show transfers without unsupported economic conclusions.
### Verification
`pnpm --dir clients/research-ui test src/research/economy.test.ts src/views/EconomyPanel.test.ts`.

## Task 19: Render collective project history
### Intent
Display accepted work/progress over time and preserve the limits of bounded contribution tails.
### Implementation Steps
1. ProjectsPanel requests objective `map?section=projects` at selected explicit/sampled boundaries, with optional exact project entity ID and signed pagination. Render project kind/status/location, labor/material required/progress, shortages, linked structure, public-act counters and accepted contribution table.
2. Build per-project step series from sampled states and event-tick contribution markers from returned accepted-contribution rows. Use composite project/actor/tick/item/labor/material identity only for presentation deduplication within identical row evidence; do not claim distinct total events from an ambiguous duplicate. Show `accepted_contribution_count` versus retained tail length and detail truncation.
3. Calculate sampled progress differences only as display differences labelled between observed boundaries; never synthesize a contribution event, founder/leader role or exact completion tick from gaps. Public-good benefits do not imply access grants or moral roles.
4. Add project selection/list paging and agent/location links. Prefix snapshots may show partial tick state but cannot join finalized captures; disclose cursor explicitly.
### Required Interfaces and Contracts
Collective project history is objective sampled state plus retained accepted receipts, not guaranteed full event history. Display full server counters separately from truncated detail. No new event history API or capture channel.
### Requirement Evidence
User collective project history; `CivilizationProjectRow` counts/tail/context and V3 public goods authority contract.
### Error Handling and Logging
Unavailable historical replay leaves available boundaries visible with gaps. Deleted/absent-at-boundary project is not assumed abandoned without status/evidence. Safe count/tick metadata only.
### Tests
Real objective project rows, cumulative counters repeated across pages, truncated contribution tail, sparse progress/completion, absent prior project, disabled channel, location/agent links and prefix/full-boundary distinction.
### Acceptance Criteria
Project timelines/table show actual accepted work/progress and all omitted-detail limits; no social authority inferred from contributions.
### Verification
`pnpm --dir clients/research-ui test src/research/projects.test.ts src/views/ProjectsPanel.test.ts`.

## Phase Risks and Mitigations
Captured counts can be cumulative or windowed: preserve the returned window and refuse unsupported summation. Community comparison never installs a society registry.

## Phase Completion Checklist
Focused spatial/economic/project behavioral tests pass; index progress updated.
