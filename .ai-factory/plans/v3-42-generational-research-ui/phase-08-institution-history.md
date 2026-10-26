# Phase 8: Institutions, offices and institutional lineage

Plan: [index.md](index.md)  
Task: 20  
Depends on: Tasks 7–9, 12, 16, 17

## Objective
Extend the existing institution screen into three navigable research lanes: timeline, office succession and institutional lineage.

## Current-Code Evidence
| Path | Symbols | Why it matters |
|---|---|---|
| `clients/research-ui/src/views/InstitutionsPanel.svelte` | generic emergence/persistence metric loader | Existing screen to extend; currently mostly scalar cards |
| `src/simulation/civilization_rows.py` | `CivilizationInstitutionRow` | Concept/office/episode, owner/native identity, lifecycle/evidence boundaries |
| `src/api/routes/lineage.py` | institution / office_succession families | Institution is analytical; office succession subjective |
| `.ai-factory/ARCHITECTURE.md` | V3-29–34 seams | Offices/legitimacy are private claims, not world permissions |

## Files to Change
Modify `clients/research-ui/src/views/InstitutionsPanel.svelte`, its test and RunOverview integration. Introduce `clients/research-ui/src/research/institutions.ts`, `institutions.test.ts`. Reuse existing LineageGraph/SeriesChart/ResearchTable, not separate graph engines.

## Task 20: Render institution timeline, office succession and institution lineage
### Intent
Make institutions longitudinally inspectable without creating objective institutions or globally authoritative occupants.
### Implementation Steps
1. Add timeline subview over captured `institutions` layer, keyed by run/evidence/identity owner/native kind/native ID plus returned episode identity. Render emerging/stable/weakening/collapsed/censored concepts/episodes and recognized/uncertain/vacant/contested/lost office claims as separate lanes.
2. Timeline spans use returned supported/evidence ticks; gaps are unknown/censored, not continuous persistence. Consecutive frames with compatible identity may be connected visually only across known captured boundaries; changed structural revision/episode remains separate.
3. Office succession subview uses `office_succession` subjective lineage scoped to one owner. Show vacant/contested/relinquished/disputed or returned status codes, claimant/occupant relations and evidence. Never choose a global `current_occupant` by majority, confidence or most recent claim.
4. Institutional lineage subview uses analytical `institution` lineage with exact snapshot, root/direction, lifecycle/lineage metric adapters and source inspector. Same label or owner-office ID across episodes is not a lineage edge; only returned evidence relates episodes.
5. Recognize source-specific institution focus. Civilization `institutions` concept/office/episode rows resolve by exact `institution_id`, `civilization_row_id`, native owner/kind and publication, using the existing overlay `entity_id` filter where appropriate and then checking the returned row. A subjective concept is not a valid subjective lineage `institution` query. Office lineage uses family `office_succession` with subjective owner; analytical episode lineage uses `institution`, omits scope owner and retains the node's required identity owner. Emit lineage links only from an exact returned node ref, not by converting a concept label/ID into an episode. Preserve source/identity/publication in share/Godot links. Existing emergence/persistence and later metric cards remain selected by exact family/version.
### Required Interfaces and Contracts
No institution type registry, political office authority, permission or law is created. Expected duties/authority/legitimacy remain private beliefs. Analytical lifecycle is a retrospective classification and never overrides an owner's status. Evidence tags accompany every row/node/edge, not just the screen heading.
### Requirement Evidence
User institution timeline, office succession, institution lineage and objective/subjective/analytical distinctions; V3-30 office identity and V3-34 censored lifecycle contract.
### Error Handling and Logging
Missing debug keeps objective run shell usable, not an objective replacement institution timeline. Missing capture and unknown focus have explicit reasons. DEBUG lane/class/count/reason only; no labels, claims or narrative content.
### Tests
Real `overlay_institutions.json`; same native ID/different owner, stable→weakening→censored/collapsed, sparse gaps, contested/vacant office, conflicting owner occupants, episode revisions, missing root and keyboard lanes. Round-trip subjective concept civilization focus, subjective office-succession ref and analytical episode ref with identity owner but no scope owner. Assert no invalid subjective institution-family request or cross-source publication query. Tests mount the component, not merely inspect source strings.
### Acceptance Criteria
All three requested institution surfaces are interactive, qualified, temporally explicit and free of objective office/permission claims.
### Verification
`pnpm --dir clients/research-ui test src/research/institutions.test.ts src/views/InstitutionsPanel.test.ts`; `pnpm --dir clients/research-ui check`.

## Phase Risks and Mitigations
Owner-local office identity and analytical episode identity differ: keep them separate in types and display. Display copy must describe private concepts rather than claim that no institution-like analytical structure can exist.

## Phase Completion Checklist
Task20 tests/acceptance pass and its checkbox is updated only in index.
