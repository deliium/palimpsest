# Phase 6: Cultural, lexical, semantic and narrative history

Plan: [index.md](index.md)  
Tasks: 15–16  
Depends on: Tasks 4–9, 12

## Objective
Make cultural trait timelines, vocabulary evolution, semantic drift and historical narrative lineage inspectable with real evidence and explicit temporal limits.

## Current-Code Evidence
| Path | Symbols | Why it matters |
|---|---|---|
| `src/analysis/cultural_evolution_evidence.py` | `InventoryBoundary`, `TraitPresence`, dimensions/coverage | Distinct inventories and denominators; no composite culture score |
| `src/analysis/semantic_drift_metrics.py` | `SemanticSenseRow`, drift/stability/divergence results | Metrics are aggregate analysis, not a historical sense stream |
| `src/api/routes/observer.py` | labels/symbolic/translation routes | Current owner overlays must not masquerade as historical capture |
| `docs/cultural-evolution-metrics.md` | six families and missing-capture contract | Inventory cannot be recovered retroactively |
| `docs/research-api.md` | generational narrative projection | Metadata-only variants/roots/sources/themes/counts; no story content |

## Files to Change
Introduce `clients/research-ui/src/research/culture.ts`, `language.ts`, `narratives.ts`, `src/views/CulturePanel.svelte`, `LanguagePanel.svelte`, `NarrativePanel.svelte` and sibling tests; add a `research/metricAdapters.ts` registry and tests shared with AnalyticsPanel. Modify AnalyticsPanel/RunOverview only to route/consume those adapters.

## Task 15: Render cultural trait timelines and vocabulary evolution
### Intent
Replace generic scalar dumps with trait-carriage and lexical-inventory views while preserving per-dimension scientific meaning.
### Implementation Steps
1. CulturePanel offers captured civilization culture by location/region/population basis and, when a matrix/cell is explicitly selected, the paged cultural inventory artifact. Do not scan all matrices to guess a run association. Validate artifact run ID matches selected run; mismatches show a clear error. Render `runtime_bound` versus `legacy_unverified` independently of capture coverage; a valid self-digest on a legacy export does not establish runtime completion.
2. `culture.ts` adapts captured carrier count/proportion over boundaries; plot each dimension/trait separately with eligible/unavailable denominator and exact capture window. For cultural evidence pages, calculate only descriptive inventory counts/distinct opaque content IDs from complete loaded boundary rows; incomplete pages remain partial. Label transformations as display summaries, not new metric families.
3. LanguagePanel Vocabulary mode shows per-owner inventory rows and per-generation carriage/distinct-form count over captured boundary rows in dimension `vocabulary`. IDs/digests are abbreviated only visually; full identity is retained for selection. Count absence as zero only for explicit complete enabled owner/dimension coverage.
4. Show current labels/symbolic/translation in a separate SUBJECTIVE as-of card when available, preserving existing safe label display behavior. Do not join cultural `content_digest` to label token by guessing hash compatibility. Stored cultural/vocabulary measurements use Task7's bounded `values.rows_json` decoder and `metricAdapters.ts` discriminants: family/algorithm/policy, measurement ID, dimension/representation/scope, partition/groups, population basis/denominator, baseline/end ticks and units. Preserve value/numerator/denominator, PRESENT/PARTIAL/UNAVAILABLE, reason, observed/expected coverage and censoring. PARTIAL rows may be displayed with qualification but never receive UI-computed inferential intervals or get pooled as complete rows.
### Required Interfaces and Contracts
No raw messages/stories, no new culture score, no assumption that term equality implies shared meaning. Missing capture leaves a visible unavailable timeline plus separately labelled available current metadata/aggregate metrics; never invent historical data. All nineteen requested views remain reachable even when their source is unavailable.
### Requirement Evidence
User cultural trait timelines/vocabulary evolution and visual distinction; V3-37 inventory coverage and dimension contracts.
### Error Handling and Logging
Selected dimension/row counts and outcome only. Missing matrix selection requests explicit user selection; capture-off, missing inventory, partial owner coverage and incompatible basis use distinct notices.
### Tests
Real `known-lineage-v1.json` through generated artifact API; complete empty versus disabled/missing owner; multi-dimension separation; partial page cannot claim full distinct count; unjoinable digests; Unicode labels; matrix/run mismatch; captured gaps remain gaps. Use real encoded cultural measurement rows to assert values, denominator, censoring and units, with nested duplicate/depth/malformed JSON rejected. Legacy-unverified evidence keeps its binding warning even with complete channel coverage.
### Acceptance Criteria
Trait and vocabulary charts show real boundary data, exact denominator/source and honest unavailable states, not fabricated smooth trajectories.
### Verification
`pnpm --dir clients/research-ui test src/research/culture.test.ts src/views/CulturePanel.test.ts src/views/LanguagePanel.test.ts`.

## Task 16: Render semantic drift and historical narrative lineage
### Intent
Show changing private meaning and transmitted narrative ancestry without asserting truth or permanent access to subjective history.
### Implementation Steps
1. LanguagePanel Semantics mode consumes Task6 history grouped by `(owner,source,local_id,term_digest)`; draw retained sense-revision transitions at exact ticks, referent/association digest changes, triggers and confidence. Title includes checkpoint tick and retained-only/prefix-unknown notice. Requested historical tick mismatch stays unavailable.
2. Stored `semantic_stability@1`, `semantic_drift@1`, `semantic_divergence@1` appear as analytical aggregate cards beside, not in place of, subjective sense rows. Show units/coverage; do not calculate a new drift probability or causal score in the UI. Current translation mappings remain a distinct private-claim view.
3. NarrativePanel uses lineage family `narrative` for snapshot-pinned graph and generational narrative metadata for one owner as-of checkpoint. Add root/variant/source-loss/witness/retelling/record/transition count inspector and ancestor/descendant traversal; branch/merge edges only when returned.
4. Distinguish objective record existence from subjective narrative content and analytical historical-alignment metrics. Do not mark a story true/false, automatically resolve declared source testimony or treat a dead witness as missing history proof. Narrative focus links retain native kind/owner/class/publication.
### Required Interfaces and Contracts
Semantic timeline is retained checkpoint evidence, not arbitrary restored history. Narrative current projection has no historical selector: show as-of/live limitation and never display it under selected historical tick without qualification. No raw narrative text or private labels added to metadata endpoints.
### Requirement Evidence
User semantic drift and historical narrative lineage; phase2 history limitation; V3-28 narrative provenance and lineage evidence contracts.
### Error Handling and Logging
Unavailable history/lineage affects its lane only; aggregate metrics can still render. Reject owner/ref mismatch before plotting. No logs of terms/digests/narrative IDs used as payload substitutes.
### Tests
Trimmed sense ordinal history, multiple meanings, label versus composition, checkpoint conflict, aggregate-versus-subjective badges; narrative branch/merge/source loss/dead witness, missing record and owner-specific focus round trips. Use real lineage metadata and constructed narrative fixtures labelled as presentation evidence.
### Acceptance Criteria
Semantic changes and narrative ancestry are interactive and evidence-scoped; no current subjective state is presented as restored history or objective truth.
### Verification
`pnpm --dir clients/research-ui test src/research/language.test.ts src/research/narratives.test.ts src/views/LanguagePanel.test.ts src/views/NarrativePanel.test.ts`.

## Phase Risks and Mitigations
Available history is incomplete by design: state that explicitly, do not broaden runner/capture ownership. Scientific metrics and UI display summaries remain separate adapters.

## Phase Completion Checklist
All cultural/language/narrative cases pass; index is the only progress ledger.
