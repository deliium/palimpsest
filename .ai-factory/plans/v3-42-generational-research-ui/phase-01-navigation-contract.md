# Phase 1: Research navigation and evidence contracts

Plan: [index.md](index.md)  
Tasks: 1–3  
Depends on: none

## Objective
Establish one URL-backed research selection model before adding panels. Preserve the existing SPA and epistemic vocabulary.

## Current-Code Evidence
| Path | Symbols | Why it matters |
|---|---|---|
| `clients/research-ui/src/deeplink.ts` | `ResearchUiDeepLink`, `parseResearchUiQuery`, builders | Existing credential-free contract; duplicate contact view and incomplete run-view registry |
| `clients/research-ui/src/router.ts` | `resolveRoute`, `pushRunRoute` | Query default currently hides pathname view; selection preservation is incomplete |
| `src/observer/research_ui_state.py` | `ResearchUiDeepLinkState`, parser/builders | Python mirror must remain compatible |
| `clients/research-ui/src/epistemic.ts` | `EPISTEMIC_CLASSES` | Retain seven existing presentation classes |
| `clients/research-ui/src/views/RunOverview.svelte` | `tabs`, `selectTab`, `openObserver` | Existing shell dispatch; institutions is not reachable from tabs |

## Files to Change
Modify the five existing files above, `clients/research-ui/src/components/Shell.svelte`, `clients/research-ui/src/router.test.ts`, `clients/research-ui/src/deeplink.test.ts`, `tests/unit/test_research_ui_state.py`. Introduce `clients/research-ui/src/research/selection.ts`, `selection.test.ts`, `capabilities.ts`, `capabilities.test.ts`, and `clients/research-ui/fixtures/research-links.json`.

## Task 1: Define canonical research selection and cross-client link fixtures
### Intent
Make generation, time, owner and entity selection explicit rather than component-local conventions.
### Implementation Steps
1. Add a readonly `ResearchSelection` in `research/selection.ts`: run ID, view, tick/event/sequence, generation index, composite cohort selection, scope owner ID, evidence class and entity focus. Cohort selection is `(cohort_generation_index, cohort_entry_tick, cohort_id)`; it is separate from the navigation generation. Entity focus is a discriminated union of agent, location, institution, narrative or technology, with separate lineage/civilization source variants for the latter research entities. Lineage focus carries family, native kind/ID, node key when known, identity owner and optional publication ID. Civilization focus carries layer, exact row identity, native kind, identity owner and separate publication ID.
2. Add views `population`, `cohorts`, `lineage`, `technology`, `culture`, `language`, `migration`, `economy`, `projects`; reuse existing `societies` and `institutions`. A lineage panel family selector provides genealogy, mentorship, knowledge, technology, narrative, institution and office succession, plus existing record family access. Do not add nineteen top-level tabs.
3. Extend TS and Python parse/build contracts additively. Keep existing run/tick/event/sequence/agent/view URLs valid. Canonical optional keys: `generation_index`, `cohort_id`, `cohort_generation_index`, `cohort_entry_tick`, `owner_id` (scope owner), `identity_owner` (native identity namespace), `evidence_class` (lowercase objective/subjective/analytical), `location_id`, `institution_id`, `narrative_id`, `technology_id`, `entity_source` (`lineage|civilization`), `native_kind`, `lineage_family`, `lineage_node_key`, `lineage_publication_id`, `civilization_row_id`, `civilization_publication_id`. Research focus builders always emit explicit source and qualification; legacy agent/location/run links need no new fields. Agent/location focus is objective; private/analytical IDs must not be matched solely by display label.
4. Introduce shared JSON cases consumed by TS, Python and later Godot tests: each valid URL, normalized state and expected canonical query; invalid URLs with reason codes. Cover escaped IDs, old aliases and credential rejection.
### Required Interfaces and Contracts
- At most one focus-ID key among agent/location/institution/narrative/technology. Reject `ambiguous_entity_focus` rather than silently prioritizing. `owner_id` qualifies a subjective identity and is not agent focus.
- Lineage focus requires `native_kind`, `lineage_family` and `evidence_class`. Subjective scope requires `owner_id` and its node `identity_owner` must agree. Analytical scope forbids API `owner_id`, while analytical node identity requires `identity_owner` for all native kinds except shared `agent`/`event`; objective node identity forbids it. Mirror `require_supported_scope_owner` / `require_lineage_owner_for_kind` from `src/simulation/lineage_identity.py`, with fixture parity tests rather than client-side key invention. Never infer identity owner from the currently selected agent. A `lineage_node_key`, when supplied, is 64 lowercase hex and must agree with the complete returned ref before display.
- `entity_source=lineage`: institution uses family `institution`/`office_succession` with their supported class/kind combinations; narrative uses `narrative`; technology uses `technology` or an explicit `knowledge` ref. `entity_source=civilization`: institution uses `institutions` rows of kind `concept|office|episode`; technology uses `technology` rows. Preserve `civilization_row_id` and native source refs to distinguish repeated content keys. Subjective institution concepts must not be sent to the analytical-only lineage institution family. Narrative has no civilization-source variant in this plan.
- Civilization-source focus carries the displayed row's exact entity ID (`institution_id` or technology `knowledge_id` in `technology_id`), row ID, evidence and identity owner. Keep `owner_id` only for subjective query scope. Publication selectors are source-specific: never send `lineage_publication_id` as a lineage HTTP query parameter or confuse it with civilization `publication_id`.
- Cohort selection includes all three identity fields. An older ambiguous ID-only selection may resolve only after loaded rows prove exactly one match; otherwise return `ambiguous_cohort_selection`. Selecting a cohort never overwrites independent generation navigation state.
- All integers are canonical nonnegative safe integers in JS; reject overflow, fractional, signed, duplicate known keys and sequence without tick. Reject owner/evidence qualifiers inconsistent with focus. Missing optional fields remain null. Preserve existing `event`/`agent` aliases with canonical-key precedence only when values agree; disagreeing aliases fail.
- `tick` is the resolved time authority. `generation_index` is a requested navigation/filter label, never pedigree depth or a substitute timestamp. Cohort ID is independent of generation.
### Requirement Evidence
User request: generation navigation and seven Godot focus dimensions. `docs/generational-runner.md` distinguishes generation, cohort, genealogy and community. `docs/lineage-explorer.md` requires qualified identities.
### Error Handling and Logging
Safe reason codes only; never log full URLs, IDs derived from labels, credentials, terms or narrative content. DEBUG may include view/focus kind and parse outcome. Unknown view falls back with an explicit warning; malformed selectors do not silently clear to overview.
### Tests
Table-driven round trips in `deeplink.test.ts`, `selection.test.ts`, `test_research_ui_state.py`; legacy cases unchanged. Malicious query keys, duplicates, overflow, ambiguous focus and wrong owner combinations fail. Include analytical node identity owner with null scope owner, subjective concept civilization focus, office-succession lineage focus, source-specific publication fields, identical cohort IDs at different entries/generations, and incomplete composite cohort identity.
### Acceptance Criteria
All new selections round-trip losslessly; old links still parse; one fixture corpus captures the language-neutral link contract.
### Verification
`pnpm --dir clients/research-ui test src/deeplink.test.ts src/research/selection.test.ts` and `uv run --frozen --python 3.12.14 pytest --cov --cov-report=term tests/unit/test_research_ui_state.py -q` pass.

## Task 2: Integrate URL state into the existing Research UI shell
### Intent
Every new screen must be reachable, bookmarkable and back/forward safe.
### Implementation Steps
1. Derive all run-view registries from the canonical list, remove duplicate contact and add missing institutions tab. Group navigation into Population, Lineage, Culture, Space, Institutions and Economy sections while retaining old tabs/routes.
2. Fix `resolveRoute`: explicit valid query view overrides pathname; an absent query view does not override pathname. Run ID in pathname wins only after rejecting a conflicting query run ID with a visible route error; malformed percent escapes resolve to not-found, not an uncaught exception.
3. `pushRunRoute` serializes the complete selection through one builder. Preserve focus/time/filter fields on tab changes; clear only panel-local paging state. Path builders use encoded IDs and remain under `/research/`.
4. Pass selection and a single `onSelectionChange(patch, historyMode)` callback from Shell/RunOverview to panels. User navigation uses push; canonicalization and transient input edits use replace. Do not introduce a second independent store.
### Required Interfaces and Contracts
`ResearchSelection` is the durable source; local state contains only request lifecycle, expanded graph nodes and temporary form inputs. Run change clears all run-bound selection. No selection change starts/advances a simulation. Existing matrix routes remain valid and carry explicit matrix/cell selection inside the matrix screen, not arbitrary filesystem paths.
### Requirement Evidence
Existing `router.ts`/`RunOverview.svelte` are the extension points; user explicitly requests extending the Research UI, not replacing it.
### Error Handling and Logging
Render an accessible route-error alert for invalid selectors; retain a credential-free recovery link. DEBUG navigation records view and reason, not query contents. Do not auto-open Godot on route changes.
### Tests
Mounted Shell/router behavioral tests for pathname-only view, explicit query override, conflicting run IDs, all new views, tab retention, reload and popstate. Replace existing source-string assertions where the touched behavior warrants mounting.
### Acceptance Criteria
Direct links and browser back/forward select the same panel and time/entity state; all old routes still work.
### Verification
`pnpm --dir clients/research-ui test src/router.test.ts`; `pnpm --dir clients/research-ui check`.

## Task 3: Define evidence-aware availability and feature discovery
### Intent
Make absence, denial and partial research coverage visibly different from zero or complete data.
### Implementation Steps
1. In new `research/capabilities.ts`, define a closed panel-source registry with endpoint, required credential capability, supported evidence classes and temporal semantics. Sources include demographics, generation markers, lineage, civilization catalogue/map/overlays/markers, stored metrics, cultural artifacts and retained semantic history.
2. Normalize source outcomes into `loading | available | empty | partial | unavailable | forbidden | error`, retaining original reason codes, coverage, requested/resolved tick, publication and continuation. A successful empty page with continuation is `partial`, not terminal empty.
3. Extend epistemic adapters for lowercase lineage and uppercase civilization classes without changing existing seven classes. Associate each rendered series/node/edge with its own class and owner; panel-level badges alone are insufficient for mixed content.
4. Define discovery as lazy per active panel. Missing debug credential prevents subjective requests and offers credential entry; it never downgrades a subjective query into an objective one.
### Required Interfaces and Contracts
Every panel renders source, evidence class, owner where applicable, observed window and coverage. Captured historical evidence is not a live checkpoint. No auto-enable capture or backend capability flag. Unknown schema/evidence combination fails closed for plotting.
### Requirement Evidence
`RULES.md` axioms; `ARCHITECTURE.md` authority boundaries; `docs/observer.md` and `docs/lineage-explorer.md` availability semantics.
### Error Handling and Logging
INFO source-load completion: endpoint template, outcome, row count, duration. DEBUG safe paging counts. WARN schema mismatch or corrupt artifact. Never dump response objects, headers or metric payloads.
### Tests
`capabilities.test.ts` covers capture-off, lifecycle-off, enabled empty, denied, partial denominator, uncaptured tick, 410 metric absent, 503 service disabled, unknown wire class and continuation-only pages.
### Acceptance Criteria
No missing/forbidden/partial source is rendered as a complete zero; objective/subjective/analytical remain distinct in model and UI.
### Verification
`pnpm --dir clients/research-ui test src/research/capabilities.test.ts src/epistemic.test.ts`.

## Phase Risks and Mitigations
The TS/Python/Godot mirrors may diverge: the shared link corpus is mandatory. Avoid expanding this task into unrelated router cleanup.

## Phase Completion Checklist
Every task above meets its acceptance criteria; verification passes; progress is recorded only in `index.md`.
