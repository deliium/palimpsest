# Implementation Plan: V3-28 Multi-Generational Historical Narratives

Branch: main (current branch; `git.create_branches: false`)
Created: 2026-10-18
Mode: full (ultra depth requested; canonical plan stem required)

## Settings

- Testing: yes
- Logging: verbose
- Docs: yes — mandatory `/aif-docs` checkpoint during implementation.
- Artifact naming: every plan artifact produced for this feature begins `v3-`; canonical file is `.ai-factory/plans/v3-28-historical-narratives.md`.
- Implementation scope: extend the owner-scoped V2 narrative ledger with witness, record, edit, merge, retelling, generation-proxy, theme, and source-loss provenance so stories can survive the deaths of every original witness. Agents never receive an objective truth label. Detached research infrastructure may compare narrative claims with objective history. **No new command, event, perception field, observer semantic type, replay/codec pair, capability flag, or Alembic migration.**

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] full mode confirmed; git.create_branches=false; resolved plan file: .ai-factory/plans/v3-28-historical-narratives.md (format=slug)
INFO [aif-plan] plan_default_milestone=auto would surface M6 first; explicit V3 scope uses M7, following v3-22 through v3-27 precedent; this plan does not close M6
INFO [aif-plan] ultra request treated as full-mode depth; this skill has no separate ultra mode
INFO [aif-plan] RESEARCH.md absent; research_influenced_plan=false
INFO [aif-plan] baseline selectors to recheck before implementation: 43 commands, 73 observer semantic types, 112 metric families, runner-config-v47, replay-v22/codec v20, Alembic 0017, latest Experiment BD
INFO [aif-plan] target selectors after this plan: 43 commands, 73 observer semantic types, 115 metric families, runner-config-v48, replay-v22/codec v20, Alembic 0017, Experiment BE

## Roadmap Linkage

Milestone: "M7 — V3 Generational Civilization"
Rationale: Extends the owned `cultural_historical_memory` and `generational_population` substrate so narratives can persist through witness death and carrier turnover while meaning, provenance, and source loss remain owner-scoped and detached analysis alone compares stories with objective history.

## Goal

Let a society keep a story alive after every original witness is dead. A narrative variant remains an owner-scoped, revisable claim that is carried through retelling, teaching, records, archives, reconstruction, and ordinary communication. It gains bounded provenance for:

- the source event or source record;
- the witnesses and retellers, including declared transmission chains;
- records read, copied, annotated, damaged, or lost;
- retellings, edits, merges, retirement, and reactivation;
- subjective source-loss state when observed deaths or record damage remove every known first-hand source;
- a small descriptive theme set covering founders, disasters, discoveries, conflicts, migrations, and innovations.

Original witness death never deletes or retires a narrative by itself. A story survives only while at least one living owner still carries it or an intact record remains available through existing channels. New agents begin blank-slate and can acquire the story only through ordinary delivery, teaching, record reading, or reconstruction.

Three layers stay separate:

- **Objective history:** committed events, lifecycle records, generation indices, death ticks, and record integrity. Agents do not receive generation indices or analysis documents.
- **Subjective narrative provenance:** the owner's private witnesses, retellings, record references, transitions, theme labels, and source-loss belief. It may be incomplete or wrong and is never an objective truth claim.
- **Analytical comparison:** detached research rows and metrics that compare narratives with objective history. Results never re-enter cognition, memory formation, prompts, admission, or observations.

## Current Implementation Evidence

- **The V2 ledger already carries lineage but not generational provenance.** `src/agents/cognition/cultural_narratives.py` `NarrativeVariant` stores `source_event_id`, `transmission_root_id`, `parent_variant_ids`, `mutation_generation`, `carrier_agent_ids`, `location_ids`, and compressed evidence. It has no witness set, record references, observed-death state, source-loss state, transition log, theme label, or declared hop count.
- **Updates read only existing owner evidence.** `apply_narrative_update` consumes one `Observation`, `OwnerSafeSocialIdentity`, the previous `NarrativeLedger`, loaded memories, and an optional `NarrativeCueSummary`. It has no death-witness pass, record cue pass, or source-loss pass. `_apply_cues` currently handles only distorted artifact cues and reconstruction cues.
- **The policy is locked to v1.** `CulturalNarrativePolicy.version` accepts only `cultural-narratives.v1`; `NarrativeLedger` rejects any other policy version. A gated v2 policy is required so disabled/off runs stay byte-identical.
- **The existing analysis substrate already knows about witness death and generations.** `src/analysis/historical_memory.py` defines `HistoricalMemoryHarvest`, `HistoricalProvenanceNodeKind.NARRATIVE_VARIANT`, `HistoricalProvenanceEdgeKind.GENERATION_SUCCESSOR`, `HistoricalMemoryTransitionCause.LAST_DIRECT_WITNESS_DIED`, `GENERATION_BOUNDARY`, and living/deceased helpers. `historical_memory_metrics.py` already computes layer transitions and queries. The new work should compose with this module instead of duplicating its graph.
- **The existing narrative metric is a lineage proxy, not a generational analysis.** `src/analysis/cultural_narrative_metrics.py` computes persistence, mutation, distortion, source-loss proxies, convergence, and spread from caller rows, but it does not join objective death ticks, generation indices, record integrity, or objective event facts.
- **Run-level channel specs already have a clean seam.** `src/simulation/runner.py` `_ChannelLoopOptions` and `_channel_loop_kwargs` bind run-level specs such as `cultural_features_spec`, `durable_records_active`, and `knowledge_repositories_active` without adding `AgentCognitionSpec` enums. A `generational_narratives` sibling can follow the same pattern.
- **The latest runner schema is v47.** `src/simulation/runner_models.py` ends at `RUNNER_SCHEMA_VERSION_V47`; the narrative schema allowlist also ends at v47. `runner-config-v48` needs a full accepted-set, exact-key-set sweep.
- **Ledger exports are incomplete.** `SimulationRunnerResult` exports `terminology_ledgers`, `symbolic_ledgers`, and `translation_ledgers`, but not owner cultural-narrative ledgers. Detached analysis needs a bounded export for narrative rows.
- **The owner narrative route is summary-only.** `src/api/routes/inspection.py` exposes `GET /v1/simulations/{run_id}/owners/{owner_id}/cultural-narratives` with `research-cultural-narratives-v1` items and no witness, record, source-loss, or generation fields.
- **Known gaps:** no witness records, no observed-death witness state, no record provenance, no edit/copy/annotation transitions, no source-loss state machine, no theme labels, no analysis-only generational comparison, no runner v48, no Experiment BE, and no focused generational narrative metrics.

## Compatibility and Authority Contract

1. `WorldEngine` remains the sole objective mutation authority. This plan adds **no** world behavior: no command, event, perception field, RNG stream, identifier namespace, or Alembic migration.
2. The closed `AgentCommand` count stays **43**. The observer semantic-type count stays **73**. Replay stays `EVENT_SCHEMA_REPLAY_V22`, persistence codec stays `v20`, `/v1` and `observer-protocol-v1` are unchanged, and Alembic head stays `0017`. Only the runner schema advances to `runner-config-v48` when the generational narrative channel is enabled.
3. No new capability flag. The plan deepens the owned `cultural_historical_memory` and `generational_population` flags. `institutional_economy` and `multi_hop_testimony_tracking` remain fail-closed.
4. `generational_narratives` is an optional run-level sibling on `runner-config-v48`. It requires exact `cultural_feature_provenance`, `population_lifecycle`, and `V3CapabilityFlags.generational_population`, plus at least one deterministic `cultural_narrative_mode`. `durable_records`, `knowledge_repositories`, and `historical_memory_layers` remain optional. Absent `generational_narratives` keeps the prior highest-active schema and the v1 narrative policy.
5. `runner-config-v48` is emitted only when `generational_narratives` is present. It accepts optional older cultural and regional siblings without implying any of them. A run with lifecycle + cultural narratives but without `generational_narratives` stays on its prior schema and v1 policy.
6. The V2 ledger remains owner-scoped. No shared story table, global narrative registry, automatic cross-agent copy, objective dictionary, or world-owned narrative exists. A listener forms its own variant from delivered content, record reading, or reconstruction.
7. **No truth field exists in the agent ledger.** `NarrativeStatus` remains a transmission lifecycle (`candidate`, `active`, `retired`, `merged`), not a truth value. Witness death and source loss are provenance states, not falsity. The ledger must not contain `true`, `false`, `correct`, `verified`, `accuracy`, `objective_truth`, or equivalent fields.
8. Witness death and source loss are **observed evidence only**. The ledger marks a witness dead only when that owner observed the death through an existing occurrence. Missing evidence leaves the state `unknown` or `partial`; it never becomes an objective claim.
9. Generation transitions are **analysis-only**. Agents never receive `generation_index`, cohort, genealogy, or analysis rows. Detached analysis joins carrier agent IDs to lifecycle/genealogy rows and `analysis.historical_memory` generation successors.
10. Records enter through existing `ArtifactInterpretationMode` and `DurableRecordsSpec` seams. Narrative record references carry opaque record IDs, revisions, integrity, copy generation, and annotation counts only; they never copy an objective mark body into another owner.
11. Analysis is detached and read-only. New analysis modules import no persistence, runtime, private world modules, or subjective ledger classes. `src/experiments/composition.py` builds detached rows and performs the join. Metric documents and logs use opaque IDs, counts, bands, and rates; no story tokens, record text, or narrative prose enter a document or log.
12. Disabled/off behavior is byte-identical: no v2 ledger fields, no witness or record collection, no policy-version change, no new RNG consumption, no trajectory change, and no cognition-fingerprint drift.
13. Presentation stays read-only. No observer semantic type, Godot layout, or protocol name changes. A researcher-only generational narrative projection may expose opaque IDs, themes, source-loss states, and counts.

## Design Decisions

### Run-level spec and gated v2 policy

- Add `GenerationalNarrativesSpec` in `src/simulation/runner_models.py` with exact keys:
  - `generational_narratives_mode` (locked to `deterministic`; `disabled` is rejected and absence means off);
  - `source_loss_policy` (locked to `observed_evidence_only`);
  - `theme_policy` (locked to `observed_kind_and_lineage`);
  - `max_witnesses` in `[1, 8]`, default `8`;
  - `max_records` in `[1, 8]`, default `8`;
  - `max_transitions` in `[1, 16]`, default `16`;
  - `max_declared_chain` in `[1, 8]`, default `8`.
- Add `default_generational_narrative_policy(...)` in `cultural_narratives.py` with `CULTURAL_NARRATIVE_POLICY_VERSION_V2 = "cultural-narratives.v2"`. Keep `cultural-narratives.v1` untouched for off runs.
- The v2 policy carries the v1 constants plus record/theme/witness caps and the record-read delta. It does not carry any truth, importance, or moral weight.
- `NarrativeLedger.policy_version` accepts exactly `{v1, v2}`. A v1 ledger must leave every v2 field empty/default; a v2 ledger may populate them. This preserves v1 identity and prevents mixed-policy ledgers.
- `apply_narrative_update` accepts `CulturalNarrativePolicy | GenerationalNarrativePolicy | None`. The v2 branch is active only when the generational policy is supplied.

### Owner-scoped provenance contracts

Add to `src/agents/cognition/cultural_narratives.py`:

- `NarrativeWitnessKind`: `first_hand`, `declared_source`, `declared_reteller`, `record_mediated`.
- `NarrativeWitness`: `witness_agent_id: AgentId`, `kind`, `hop_index`, `first_seen_tick`, `last_seen_tick`, `death_observed_tick: int | None`. Only agents the owner can bind through `OwnerSafeSocialIdentity` become witnesses. Unknown declared entities stay in a separate declared-reference tuple.
- `NarrativeRecordRole`: `authored`, `read`, `copied`, `amended`, `annotated`, `damaged`, `partially_lost`, `destroyed`.
- `NarrativeRecordRef`: `record_id: str`, `role`, `observed_revision`, `copy_generation: int | None`, `integrity: str | None`, `annotation_revisions: int | None`, `tick`. No mark text, relations, or prose.
- `NarrativeTransitionKind`: `minted`, `retold`, `record_read`, `record_copied`, `record_amended`, `record_annotated`, `record_damaged`, `merged`, `edited`, `first_hand_witness_died`, `all_witnesses_dead`, `source_lost`, `retired`, `reactivated`.
- `NarrativeTransition`: `transition_id`, `kind`, `tick`, `parent_variant_ids`, `carrier_agent_id: AgentId | None`, `record_id: str | None`, `hop_index: int | None`. Stable ID from owner/variant/kind/tick/reference.
- `NarrativeSourceLossState`: `intact`, `partial`, `lost`, `unknown`.
- `NarrativeSourceLossReason`: `none`, `some_witnesses_dead`, `all_first_hand_witnesses_dead`, `record_damaged`, `record_destroyed`, `witness_and_record_loss`, `unknown`.
- `NarrativeSourceLoss`: `state`, `reason`, `tick: int | None`, `known_witness_count`, `dead_witness_count`, `record_backed`.
- `NarrativeTheme`: `founders`, `disasters`, `discoveries`, `conflicts`, `migrations`, `innovations`, `unclassified`.
- `NarrativeThemeBasis`: `observed_occurrence_kind`, `inherited_lineage`, `unclassified`.
- `narrative_transition_id`, `narrative_witness_id`, and `narrative_record_ref_id` stable-ID helpers.

Extend `NarrativeVariant` with defaulted fields after existing fields:

- `source_witnesses: tuple[NarrativeWitness, ...] = ()`;
- `declared_source_entity_ids: tuple[str, ...] = ()`;
- `declared_hop_count: int = 0`;
- `first_hand: bool = False`;
- `record_refs: tuple[NarrativeRecordRef, ...] = ()`;
- `transitions: tuple[NarrativeTransition, ...] = ()`;
- `source_loss: NarrativeSourceLoss | None = None`;
- `themes: tuple[NarrativeTheme, ...] = ()`;
- `theme_basis: NarrativeThemeBasis = NarrativeThemeBasis.UNCLASSIFIED`.

Validation requirements:

- witness IDs unique by agent, hop indices non-negative, death tick not before first-seen tick;
- record IDs unique by `(record_id, observed_revision, role)`, revisions and copy generations non-negative;
- transition IDs unique, parent IDs cannot equal the containing variant, caps enforced;
- source-loss counts consistent with witness records and reason, tick not before `first_tick`;
- themes unique, ordered by closed enum order, `unclassified` never mixed with classified themes;
- v1 ledgers reject any non-empty v2 field;
- owner consistency across witnesses, records, and transitions;
- reject analysis rows, metric documents, `WorldEvent`, private world types, and another owner's ledger.

### Witness and death tracking

- `_apply_observed_events` mints a first-hand variant when the owner directly observes an occurrence. When the v2 policy is active, add the owner as `NarrativeWitnessKind.FIRST_HAND` at hop `0`, set `first_hand=True`, set `source_event_id`, derive themes from the observed occurrence kind, and append a `minted` transition.
- `_apply_witness_deaths` runs every update after retellings and record cues. It scans `observation.occurrences` for the closed death kinds (`died`, plus any existing death-causing occurrence kind the observation already exposes) and maps `actor_id`, `target_id`, and `other_entity_id` to agent IDs through `OwnerSafeSocialIdentity.counterparts`.
- A matched death updates the witness `death_observed_tick` and appends `first_hand_witness_died`. Death is never inferred from absence, analysis, or another owner's ledger.
- A variant is not retired, weakened, or deleted merely because a witness died. Retirement remains strength-based. The current owner is alive by definition, so a first-hand owner cannot become an all-dead source.
- Unknown declared chain entities stay in `declared_source_entity_ids` and do not affect subjective `source_loss` counts until the owner can bind them to an agent.

### Retelling and record channels

- `_apply_retells` parses the world-verified delivery plus the speaker-declared `source_agent_chain`, `hop_count`, `immediate_source_id`, `root_communication_id`, and `source_basis`.
- Known chain agents become `declared_source` at hop `0` and `declared_reteller` at later hops. The listener is a carrier, not a source witness. The variant records `declared_hop_count` and appends a `retold` transition. A declared chain is testimony, not objective truth.
- `NarrativeCueSummary` gains a `records` tuple of a new `NarrativeRecordCue` value built only by `CognitiveLoop`. Each cue carries record ID, observed revision, distorted flag, source tick, copy generation, integrity, annotation revisions, lost-mark count, and the owner's private readings already present in `ArtifactInterpretation`.
- `_apply_record_cues` mints or reinforces a `NarrativeOrigin.DURABLE_RECORD` variant with `NarrativeEvidenceChannel.RECORD`, a `NarrativeRecordRef`, and a `record_read` transition. A higher observed revision appends `record_amended`; an annotation appends `record_annotated`; a copied record appends `record_copied`; an observed damage/loss occurrence appends `record_damaged`.
- A record reading never copies another owner's ledger, a mark body, or an objective truth claim. It only creates the owner's own structured content from the owner's interpretation.
- `_apply_cues` continues to handle distorted artifact and reconstruction cues exactly as v1. Record cues are additive and only active under the v2 policy.
- Merges continue to union content and parents. Under v2, a merge also unions parent themes, caps the result, records the parent IDs, and appends a `merged` transition. Narrative content mutations append `edited`; record amendments and annotations append `record_amended` or `record_annotated`.

### Source-loss state machine

`_update_source_loss` recomputes each variant's subjective state from the owner's own evidence:

1. **`intact`**: at least one known first-hand witness is not observed dead, or at least one intact record reference exists. `record_backed` is true when an intact record is the preserving source.
2. **`partial`**: some but not all known first-hand witnesses are observed dead, or a known record is damaged but the variant still has another source. Reason is `some_witnesses_dead` or `record_damaged`.
3. **`lost`**: every known first-hand witness is observed dead and no intact record remains, or every known source is lost through observed record destruction plus witness death. Reason is `all_first_hand_witnesses_dead`, `record_destroyed`, or `witness_and_record_loss`.
4. **`unknown`**: no known first-hand witness and no record evidence. Missing evidence is never treated as loss.

Rules:

- `lost` records provenance loss only. It does not mark the story false, lower its strength, retire it, or prevent retelling.
- If all original witnesses are dead but the current owner carries the story, the variant remains `active` or decays only by the existing strength rule.
- If a later record is read or a living witness is discovered, the state can return to `intact` or `partial` and append `reactivated` where appropriate.
- Analysis compares this subjective state with objective death ticks and record integrity; the comparison never flows back.

### Theme labels

- Derive themes only from evidence the owner already has: the observed occurrence kind and theme inheritance through retelling, record, reconstruction, and merge.
- Closed deterministic mapping (locked in code, not configurable): founder-entry kinds → `founders`; death/harm/artifact-loss kinds → `disasters`; attack/flee kinds → `conflicts`; journey/region-entry kinds → `migrations`; experiment/craft/production/technique/structure success kinds → `discoveries` and/or `innovations`.
- A variant may carry more than one theme, capped at three. Retellings, record readings, reconstructions, and merges inherit parent themes. If no closed mapping applies, the theme is `unclassified`.
- A theme is a retrieval and analysis grouping label. It creates no story, changes no strength, asserts no importance, and never designates truth. The engine never generates a founder story, disaster story, or heroic narrative.

### Generation transitions are analysis-only

- The ledger records carrier agent IDs, declared hop counts, source witnesses, and transitions. It does **not** record `generation_index`, cohort, or objective genealogy.
- Detached analysis joins carrier IDs to `AgentCreated.generation_index`, `initial_lifecycle_records`, or `generation_index_by_agent` and to `analysis.historical_memory` `GENERATION_SUCCESSOR` edges.
- The analysis reports generation span, first generation, last generation, carrier turnover, and generation-boundary transition counts. These values never enter a prompt, observation, memory, belief, or admission path.
- `multi_hop_testimony_tracking` remains fail-closed; this plan uses existing declared-chain testimony only.

### Detached rows and metric families

Create `src/analysis/generational_narratives.py` with duck-typed row builders so analysis imports no subjective ledger type.

- `NarrativeGenerationRow`: owner, variant, root, source event, themes, status, origin, first/last tick, carrier count, carrier generation values, generation span, witness counts, dead-witness counts, record counts, transition counts, hop count, source-loss state, record-backed flag.
- `NarrativeRecordRow`: owner, variant, record ID, role, revision, copy generation, integrity, annotation revisions, tick, source-loss relation.
- `NarrativeSourceLossRow`: owner, variant, subjective state/reason, objective source-loss state, dead-witness share, record integrity summary, all-witnesses-dead flag.
- `NarrativeHistoryComparisonRow`: owner, variant, source event, objective event kind, actor/target/location tokens, objective tick, narrative tick, token coverage, participant coverage, location agreement, temporal distance, and an analysis-only `aligned` / `partial` / `divergent` / `unverifiable` class.
- Builders: `narrative_generation_rows_from_ledgers`, `narrative_record_rows_from_ledgers`, `narrative_source_loss_rows_from_ledgers`, `narrative_history_comparison_rows_from_rows`, and `generational_narrative_inputs_from_harvest`.

Compose with `analysis.historical_memory`:

- Build the existing harvest with `narrative_rows`, `artifact_rows`, `witness_rows`, death ticks, and generation maps.
- Use `HistoricalMemoryTransitionCause.LAST_DIRECT_WITNESS_DIED`, `GENERATION_BOUNDARY`, the `NARRATIVE_VARIANT` and `AGENT` nodes, and `answer_historical_memory_queries` for objective all-witness-dead and stories/artifact-only evidence.
- Do not duplicate the provenance graph or import ledger classes.

Register three metric families:

1. `generational_narrative_continuity@1` — active lineages, generation span, multi-generation lineage rate, first-hand-to-retold rate, all-witnesses-dead survival rate, record-backed survival rate, carrier turnover, mean provenance hops, theme counts.
2. `narrative_source_loss@1` — subjective and objective source-loss rates, dead-witness share, all-witnesses-dead count, record-backed count, record-damage/destruction reasons, state/reason distributions.
3. `narrative_historical_alignment@1` — source-event coverage, participant coverage, location agreement, temporal distance, and analysis-only aligned/partial/divergent/unverifiable rates. `unverifiable` is a coverage gap, never a zero or a truth verdict.

Metric count moves **112 → 115**. Empty inputs yield `absent`, not zero. Documents expose counts, rates, bands, and opaque IDs only.

### Experiment BE

Create `src/experiments/generational_narratives_scenario.py` and register off-gate Experiment BE (`generational_narratives@1`).

Diagnostic arms:

- `be-off`: V2 narrative-only arm on the prior schema, no lifecycle, no generational spec.
- `be-witness-death`: multi-generation lifecycle; a founder observes a founding/disaster event, retells it, dies; a living child and grandchild continue the story.
- `be-record-backed`: founders inscribe a record, die, and later carriers read the record; the story survives through the record.
- `be-record-loss`: record damage/destruction plus founder death; the story survives in a carrier while source-loss state becomes `lost`.
- `be-merge-edit`: retold variants merge and records are annotated; transitions include `retold`, `edited`, and `merged`.
- `be-theme-coverage`: founder, disaster, discovery, conflict, migration, and innovation observations across arms; no arm forces a theme.
- `be-objective-comparison`: scheduled objective events and narrative claims produce aligned, partial, divergent, and unverifiable analysis rows; agents receive none of them.
- `be-unsupported`: missing lifecycle, missing cultural provenance, or missing generational flag fails closed with a stable code.

Arbiter requirements:

- Off arms have no v2 fields and no policy-version change.
- On arms remain bounded and monotonic; witness, record, and transition caps hold.
- All-witness-dead narratives remain in living carrier ledgers and are not auto-retired.
- Source loss follows observed death and record evidence; no arm injects objective truth into a ledger.
- At least one lineage spans multiple objective generations and at least one lineage survives all first-hand witnesses.
- No agent receives generation indices, candidate communities, objective history rows, or metric documents.
- No scripted founder worship, heroization, moral verdict, or forced convergence.

### Presentation and documentation

- Add a researcher-only generational narrative projection and route. It exposes variant IDs, status, origin, themes, source-loss state/reason, witness/dead/record/transition counts, carrier count, hop count, first/last tick, and opaque root/source IDs. It never exposes story tokens, record text, or another owner's ledger.
- Keep the existing `research-cultural-narratives-v1` route unchanged.
- No Godot layout, observer semantic type, protocol, or objective frame changes.

## Commit Plan

Commit messages are suggestions for implementation; this planning command creates no commits.

- **Commit 1** (tasks 1–2): `feat(v3): add generational narrative contracts and runner-config-v48`
- **Commit 2** (tasks 3–5): `feat(v3): carry witness and retelling provenance across generations`
- **Commit 3** (tasks 6–8): `feat(v3): add record, source-loss, theme, and non-truth invariants`
- **Commit 4** (tasks 9–12): `feat(v3): add detached generational narrative metrics`
- **Commit 5** (tasks 13–14): `feat(v3): add Experiment BE and generational narrative research overlay`
- **Commit 6** (tasks 15–16): `docs(v3): document historical narratives and reconcile compatibility gates`

## Tasks

### Phase 1 — Contracts and configuration

- [x] **Task 1: Define the generational narrative provenance contracts with exact validation.**
  - Files: update `src/agents/cognition/cultural_narratives.py`, `src/agents/cognition/__init__.py`; create `tests/unit/test_generational_narrative_contracts.py`; update `tests/unit/test_cultural_narratives.py`.
  - Deliver `CULTURAL_NARRATIVE_POLICY_VERSION_V2`, `GenerationalNarrativePolicy`, `default_generational_narrative_policy`, `NarrativeWitnessKind`, `NarrativeWitness`, `NarrativeRecordRole`, `NarrativeRecordRef`, `NarrativeTransitionKind`, `NarrativeTransition`, `NarrativeSourceLossState`, `NarrativeSourceLossReason`, `NarrativeSourceLoss`, `NarrativeTheme`, `NarrativeThemeBasis`, and the three stable-ID helpers.
  - Extend `NarrativeVariant` and `NarrativeLedger` with the defaulted v2 fields. Update `_freeze` and `empty_narrative_ledger` to accept the active policy version. Preserve every v1 constructor and validation path. A v1 ledger must reject any populated v2 field. A v2 ledger accepts v1-compatible content plus the new provenance.
  - Enforce owner consistency, unique witnesses/records/transitions, caps, tick ordering, source-loss consistency, theme ordering, and rejection of foreign ledgers, analysis rows, metric documents, `WorldEvent`, and private world types.
  - Forbid truth-bearing fields and values: no `true`, `false`, `correct`, `verified`, `accuracy`, `objective_truth`, or equivalent. `NarrativeStatus` stays a transmission lifecycle.
  - Acceptance: v1 and v2 contracts round-trip; caller mutation cannot alter frozen values; an all-witness-dead variant is representable with `source_loss.state=lost` and a non-empty witness list; a record-backed variant is representable with `source_loss.state=intact`; themes can be multi-valued or `unclassified`; v1 ledgers remain byte-identical.
  - Logging: DEBUG at construction boundaries with counts and safe reason codes only; INFO once per v2 ledger with variant/witness/record/transition counts. Never log story tokens, record text, themes as prose, or witness payloads.
  - Dependencies: none.

- [x] **Task 2: Gate and serialize `runner-config-v48` and the run-level spec.**
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `src/simulation/runner.py`, `src/experiments/matrix_schema.py`, `src/simulation/__init__.py`; create `tests/unit/test_runner_config_v48.py`; update `tests/unit/test_runner_config_v47.py`, `tests/unit/test_compatibility_matrix.py`, `tests/unit/test_v3_flag_defaults.py`, and matrix schema tests.
  - Add `GenerationalNarrativesSpec` with the exact keys and ranges in the design section. Add `generational_narratives` to `SimulationRunnerConfig`.
  - Add `RUNNER_SCHEMA_VERSION_V48 = "runner-config-v48"`, `_v48_family_root_keys` based on the active lower family root plus `generational_narratives`, the v48 root keyset, and every accepted-set/allowlist/encode/decode branch that currently tops out at v47. Add `generational_narratives` to `finalize_matrix_cell_config` highest-wins selection without implying any sibling.
  - Gates: `generational_narratives` requires v48; v48 requires the spec; the spec requires exact `cultural_feature_provenance`, `population_lifecycle`, `V3CapabilityFlags.generational_population`, and at least one deterministic `cultural_narrative_mode`. Optional durable records, repositories, layers, and regional siblings are accepted but never implied.
  - Add `_generational_narratives_loop_kwargs` to `_ChannelLoopOptions`/`_channel_loop_kwargs` so `CognitiveLoop` receives the spec without a new `AgentCognitionSpec` enum.
  - Plumb the v2 policy version and spec digest into `CognitionLoopConfig.condition_fingerprint_material` (extend `_cognition_config_for` to accept the run-level spec digest, or set an equivalent explicit field before config construction) so on/off runs cannot share a cognition fingerprint.
  - Acceptance: v1–v47 keysets and selectors unchanged; v48 round-trips with the required spec and optional siblings; v48 never implies a sibling; default write stays v4; missing lifecycle/provenance/flag fails closed; lifecycle + cultural without the spec stays on the prior schema with v1 narrative behavior.
  - Logging: INFO at activation with schema, mode, and channel counts; DEBUG gate decisions; WARN invalid combinations with safe codes only. No config dumps or narrative content.
  - Dependencies: 1.

- [x] **Task 3: Carry and export the narrative ledger through runtime, checkpoints, and runner results.**
  - Files: `src/simulation/agent_runtime.py`, `src/simulation/run_control.py`, `src/simulation/runner.py`, `src/simulation/runner_models.py`, `src/simulation/perception.py`, `src/simulation/new_agent_initialization.py`, `src/agents/cognition/models.py`; create `tests/unit/test_generational_narrative_runtime_carry.py`, `tests/unit/test_generational_narrative_blank_slate.py`; update cultural narrative runtime tests.
  - Add `export_cultural_narratives()` to `AgentRuntime` and `cultural_narrative_ledgers` to `SimulationRunnerResult`. Export owner-ordered ledgers, skip `None`, preserve owner order, and do not mutate ledgers. Keep the versioned result document unchanged.
  - Verify `SubjectiveSnapshot`, `AgentRuntimeCheckpoint`, commit/restore, fork, and `build_perspective` carry the extended ledger without new fields or stores. The existing `cultural_narratives` blank-slate deny-list entry remains sufficient; add a test that new agents start with no v2 provenance.
  - Acceptance: enabled runs expose one bounded ledger per owner; disabled runs expose empty tuples; restore/fork preserve witnesses, records, transitions, source loss, and themes; event/replay/codec documents are unchanged; blank-slate agents cannot inherit a story.
  - Logging: INFO once at export with ledger/variant counts; DEBUG per owner with witness/record/transition counts only. Never log story tokens or record text.
  - Dependencies: 1, 2.

### Phase 2 — Cognition

- [x] **Task 4: Track witnesses and observed deaths without asserting objective truth.**
  - Files: `src/agents/cognition/cultural_narratives.py`; create `tests/unit/test_narrative_witnesses.py`, `tests/unit/test_narrative_source_loss.py`; update cultural narrative update tests.
  - Implement `_apply_witness_deaths` and the witness bookkeeping in `_apply_observed_events`. Map death occurrences to known agents only through `OwnerSafeSocialIdentity.counterparts`. Add the owner as a first-hand witness on direct observation. Preserve unknown declared entities separately.
  - Implement `_update_source_loss` with the four-state machine. A variant is never retired or weakened by witness death. All-witnesses-dead remains representable and can be reactivated by a later record or living source.
  - Acceptance: a first-hand owner who remains alive keeps the state `intact`; observing the death of every declared first-hand witness yields `lost` when no intact record exists; a partial set yields `partial`; no evidence yields `unknown`; missing deaths never become loss; an all-dead lineage remains active under the normal strength rule.
  - Logging: DEBUG per update with owner, variant, state, reason, witness counts, and dead counts only; INFO once per changed source-loss state with aggregate counts. Never log witness identities beyond opaque IDs or any story content.
  - Dependencies: 1, 3.

- [x] **Task 5: Track retellings, declared chains, and hop provenance.**
  - Files: `src/agents/cognition/cultural_narratives.py`; create `tests/unit/test_narrative_retellings.py`; update retelling and communication tests.
  - Parse `StructuredUtterance.declared.source_agent_chain`, `hop_count`, `immediate_source_id`, `root_communication_id`, and `source_basis`. Add known chain agents as `declared_source`/`declared_reteller` witnesses, record declared entity IDs, update `declared_hop_count`, and append a `retold` transition.
  - Keep the listener a carrier, not a source witness. A declared chain is testimony. Do not copy the speaker's ledger, belief, relationship, or source-loss state.
  - Acceptance: a direct observation is hop `0` and first-hand; a retelling adds the declared chain with hop indices; a listener becomes a carrier but not a first-hand witness; repeated retellings are bounded; a forged or incomplete declared chain is representable as testimony but never promoted to objective truth; disabled/v1 runs are unchanged.
  - Logging: DEBUG with owner, variant, hop count, chain count, and added witness count only. Never log entity IDs as content surrogates or story tokens.
  - Dependencies: 4.

- [x] **Task 6: Add record cues, edits, merges, and theme labels.**
  - Files: `src/agents/cognition/cultural_narratives.py`, `src/agents/cognition/loop.py`; create `tests/unit/test_narrative_records.py`, `tests/unit/test_narrative_transitions.py`, `tests/unit/test_narrative_themes.py`; update artifact and merge tests.
  - Add `NarrativeRecordCue` and `NarrativeCueSummary.records`. Build record cues in `_build_narrative_cue_summary` from `artifact_interpretations` plus the owner's observation, only when durable records are active. Add `_apply_record_cues` for authored/read/copied/annotated/damaged records.
  - Record refs carry opaque IDs, revision, copy generation, integrity, annotation count, and tick. A narrative content revision appends `edited`; a record amendment appends `record_amended`; a record copy appends `record_copied`; a record annotation appends `record_annotated`. A damage/loss occurrence appends `record_damaged`.
  - Extend merge to union parent themes, preserve parent IDs, and append `merged`. Extend retelling/record revision paths with `edited`. Derive themes from the closed occurrence-kind mapping and inherit them through retelling, record, reconstruction, and merge. Cap themes at three and allow `unclassified`.
  - Acceptance: record readings mint or reinforce a `DURABLE_RECORD` variant with a record ref; a copied record tracks copy generation; an annotated record tracks revision; a damaged record updates source loss; a merge unions themes and parents; a retold variant inherits themes; no record or theme path adds a command, event, or world behavior.
  - Logging: DEBUG per cue/merge with record role, revision delta, transition kind, and theme count only. Never log mark text, record content, or story tokens.
  - Dependencies: 4, 5.

- [x] **Task 7: Wire the generational policy and record cues into the cognitive loop.**
  - Files: `src/agents/cognition/loop.py`, `src/agents/cognition/configuration.py`, `src/simulation/runner.py`; create `tests/unit/test_generational_narrative_loop.py`; update loop/config tests.
  - Accept `generational_narratives_spec` through `_ChannelLoopOptions`, construct `GenerationalNarrativePolicy`, and use it only when at least one deterministic narrative mode is active. Pass `observation` and `durable_records_active` into `_build_narrative_cue_summary`.
  - Add the policy version and spec digest to the cognition condition fingerprint. Keep the existing `cultural_narrative_mode` as the only per-agent mode; no new enum.
  - Acceptance: enabled runs use v2 policy; disabled runs and runs without the spec use v1 and are byte-identical; record cues are absent when durable records are off; the loop allocates no new RNG, stage, or component; the v2 policy is deterministic for identical observations.
  - Logging: INFO at mode activation with policy version and caps; DEBUG per tick with variant/witness/record/transition counts only. Never log story tokens, record text, or declared chain payloads.
  - Dependencies: 2, 6.

- [x] **Task 8: Lock all-witness-dead survival and the non-truth invariants.**
  - Files: `src/agents/cognition/cultural_narratives.py`; create `tests/unit/test_generational_narrative_persistence.py`, `tests/architecture/test_v3_generational_narratives_analysis_only.py`; update existing narrative tests and architecture isolation tests.
  - Add explicit tests that an all-first-hand-witnesses-dead variant remains in the ledger, is not retired by that fact, can be retold to a new carrier, and can return to `intact` after a record read. Add negative tests for every forbidden truth field and for analysis imports in cognition.
  - Add boundary tests that the ledger rejects `WorldEvent`, `MetricDocument`, `HistoricalMemoryHarvest`, another owner's ledger, and analysis rows. Add a source-level guard that `src/analysis` does not import `agents.cognition.cultural_narratives`.
  - Acceptance: all-witness-dead survival is explicit and deterministic; source loss never changes strength/status by itself; no truth field exists; analysis remains detached; the existing v1 behavior is unchanged when the spec is absent.
  - Logging: DEBUG with persistence/source-loss state and counts only; no story content.
  - Dependencies: 4–7.

### Phase 3 — Detached analysis and metrics

- [x] **Task 9: Define detached generational narrative rows and harvest them.**
  - Files: create `src/analysis/generational_narratives.py`; update `src/analysis/__init__.py`, `src/experiments/composition.py`, `src/experiments/collectors.py`, `src/analysis/metric_service.py`, `src/analysis/models.py`, `src/experiments/metric_collection.py`; create `tests/unit/test_generational_narrative_rows.py`, `tests/unit/test_generational_narrative_harvest.py`.
  - Deliver `NarrativeGenerationRow`, `NarrativeRecordRow`, `NarrativeSourceLossRow`, `NarrativeHistoryComparisonRow`, `GenerationalNarrativeInputs`, and the row builders listed in the design section.
  - Extend `historical_memory_harvest_from_run` to build when either `historical_memory_layers` or `generational_narratives` is present. When layers are off, pass a `None` layer spec but still supply narrative rows, artifact rows, death ticks, and generation maps. Keep the existing historical-memory metric families gated on the layers spec.
  - Harvest `cultural_narrative_ledgers` from `arm` or `arm.runner_result`, events, artifact rows, lifecycle records, and generation maps. Project only bounded fields; never import ledger classes inside `analysis`.
  - Acceptance: rows round-trip; raw story tokens never appear in row reprs or logs; generation span is derived from objective rows; subjective source-loss state and objective source-loss state are both representable; missing generation maps yield coverage gaps, not zero; identical inputs produce identical ordering and digests; analysis modules import no persistence, runtime, or subjective ledger types.
  - Logging: DEBUG with row/coverage counts and source kinds; INFO once per harvest. Never log story tokens, record text, or witness payloads.
  - Dependencies: 3–8.

- [x] **Task 10: Implement `generational_narrative_continuity@1`.**
  - Files: `src/analysis/generational_narratives.py`, `src/analysis/specifications.py`; create `tests/unit/test_generational_narrative_continuity_metrics.py`.
  - Compute active lineage count, mean/max generation span, multi-generation lineage rate, first-hand-to-retold rate, all-witnesses-dead survival rate, record-backed survival rate, mean carrier turnover, mean provenance hops, and theme counts. Use `analysis.historical_memory` generation successors and layer transitions.
  - Acceptance: empty inputs yield `absent`; a single-generation run reports a zero span and no multi-generation rate rather than a fabricated generation; an all-witnesses-dead lineage counts as surviving when a living carrier remains; record-backed survival requires an intact record; themes are counted, never judged.
  - Logging: INFO at assembly with family id and availability; DEBUG with aggregate counts only.
  - Dependencies: 9.

- [x] **Task 11: Implement `narrative_source_loss@1`.**
  - Files: `src/analysis/generational_narratives.py`, `src/analysis/specifications.py`; create `tests/unit/test_narrative_source_loss_metrics.py`.
  - Compute subjective and objective source-loss rates, dead-witness share, all-witnesses-dead count, record-backed count, and distributions for `some_witnesses_dead`, `all_first_hand_witnesses_dead`, `record_damaged`, `record_destroyed`, and `witness_and_record_loss`.
  - Compare the owner's subjective state with objective death/record evidence, but only as an analysis report. A subjective `unknown` is a coverage gap, not a false claim and not a zero.
  - Acceptance: no witnesses and no records yield `unknown`; partial death yields `partial`; all witnesses dead with an intact record yields `intact` and `record_backed`; all witnesses dead with no record yields `lost`; the metric never re-enters cognition.
  - Logging: INFO at assembly with availability and state counts; DEBUG with aggregate reasons only. Never log story content.
  - Dependencies: 9.

- [x] **Task 12: Implement `narrative_historical_alignment@1` and register all three families.**
  - Files: `src/analysis/generational_narratives.py`, `src/analysis/specifications.py` (`METRIC_FAMILY_COUNT` 112 → 115), `src/analysis/metric_service.py`, `src/analysis/serialization.py`, `src/analysis/__init__.py`, `src/experiments/metric_collection.py`; create `tests/unit/test_narrative_historical_alignment_metrics.py`; update every unit test that pins `METRIC_FAMILY_COUNT == 112`.
  - Compute source-event coverage, participant coverage, location agreement, mean temporal distance, and aligned/partial/divergent/unverifiable rates. Use detached objective event rows only.
  - Classification is analysis-only and uses a locked ±2-tick window: `aligned` when the source event matches and at least one opaque participant/location token agrees with the objective row inside the window; `partial` when the source event matches but only one of participant/location is available or the tick is inside the window with no participant/location evidence; `divergent` when the source event matches but no participant/location token agrees or the tick is outside the window; `unverifiable` when no source event or objective row exists. `unverifiable` is excluded from the alignment denominator.
  - Add `GENERATIONAL_NARRATIVE_CONTINUITY`, `NARRATIVE_SOURCE_LOSS`, and `NARRATIVE_HISTORICAL_ALIGNMENT` specifications with evidence inputs, denominators, zero-holding policies, and value keys. Add metric-service branches behind the existing safe wrapper. Update serialization allowlists and count pins.
  - Acceptance: catalog validation passes at 115; all three families are discoverable; flags-off runs stay green and omit or mark families absent; documents expose only counts, rates, bands, and opaque IDs; alignment is never called truth and never flows back.
  - Logging: INFO at assembly with each family id and availability; WARN on absent/degraded inputs with safe codes only.
  - Dependencies: 9–11.

### Phase 4 — Experiment and research surface

- [x] **Task 13: Add Experiment BE and dispatch.**
  - Files: create `src/experiments/generational_narratives_scenario.py`; update `src/experiments/catalog.py`, `src/experiments/__init__.py`, `src/experiments/coordinator.py`, `src/experiments/matrix_runner.py`, `src/experiments/matrix_schema.py`; create `tests/unit/test_experiment_be.py`; update off-gate matrix and catalog tests.
  - Implement the arms and arbiter described in the design section. Reuse the existing lifecycle, cultural feature, durable record, historical memory, and regional scenario seams. At least one arm is cognition-driven through normal observation and deliberation; diagnostic arms may use explicit commands but must not add world behavior.
  - Arbiter: off arms have no v2 fields; on arms have bounded witnesses/records/transitions; all-witness-dead lineages persist; source loss follows observed evidence; generation span is at least two for the generational arms; record-backed lineages require an intact record; no agent receives objective history or analysis results; no arm forces a theme or a moral verdict.
  - Acceptance: all arms run deterministically under the same seed/scenario identity where applicable; catalog/count assertions update; unsupported configs fail closed with stable codes; no arm claims truth, convergence, heroization, or forced persistence.
  - Logging: INFO at scenario build/arbitration with arm id and aggregate counts; DEBUG with safe structural details only. Never log story tokens, record text, or witness payloads.
  - Dependencies: 3–12.

- [x] **Task 14: Add the researcher-only generational narrative projection and route.**
  - Files: `src/simulation/subjective_projections.py`, `src/api/observer_schemas.py`, `src/api/routes/inspection.py`; create `tests/unit/test_generational_narrative_overlay.py`, `tests/unit/test_generational_narrative_route.py`.
  - Add `GenerationalNarrativeProjection` / item summary with schema `research-generational-narratives-v1` and `GET /v1/simulations/{run_id}/owners/{owner_id}/cultural-narratives/generational`. Expose variant IDs, status, origin, themes, source-loss state/reason, witness/dead/record/transition counts, carrier count, hop count, first/last tick, and opaque root/source IDs.
  - Keep `/cultural-narratives` unchanged. The route reads only the owner checkpoint, stays behind the existing debug dependency, and never exposes another owner's ledger or raw story content.
  - Acceptance: the overlay round-trips; disabled owners return an empty overlay; objective frames, `KNOWN_TYPES`, observer semantic count, protocol, and Godot layout are unchanged; existing observer tests and count pins remain green.
  - Logging: INFO at route completion with run id, owner id, variant count, and duration only; WARN on unavailable checkpoint with a safe code. Never log story content.
  - Dependencies: 3–8.

### Phase 5 — Documentation and verification

- [x] **Task 15: Update documentation and compatibility notes.**
  - Files: `docs/architecture.md`, `docs/configuration.md`, `docs/analysis-metrics.md`, `docs/experiments.md`, `docs/research-api.md`, `docs/persistence.md`, `docs/cognition-runtime.md`, `docs/development.md`, `README.md` (index if needed), `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`.
  - Document the owner-scoped witness/record/transition/source-loss/theme contract, the v2 policy gate, the fact that witness death does not retire a story, the absence of an agent truth field, the analysis-only alignment comparison, runner-config-v48 and its exact gates, unchanged replay-v22/codec v20/Alembic `0017`/43 commands/73 observer semantic types, Experiment BE, and the three metric families at 112 → 115.
  - Acceptance: docs match code selectors; no stale claim of a new command, event, observer semantic type, capability flag, or replay/codec pair; all internal links resolve; no truth, heroization, convergence, or causal-influence claim; examples are metadata-only.
  - Logging: not applicable to docs; examples must not include story tokens, record text, or witness payloads.
  - Dependencies: 12–14.

- [x] **Task 16: Reconcile architecture, compatibility, and full verification gates.**
  - Files: tests and any narrowly required wiring discovered by verification; do not weaken gates. Update `tests/architecture/` isolation/import tests, all count pins, compatibility tests, matrix schema tests, and the V1/V2/V3 flags-off suite.
  - Verify: focused generational narrative suites; `uv run --frozen --python 3.12.14 pytest`; Ruff; mypy; import-linter; architecture isolation; `tests/unit/test_v1_regression_gate.py`; `tests/unit/test_v2_scientific_invariants.py`; `tests/unit/test_compatibility_matrix.py`; Experiment BE focused suite; Experiment BB/BC/BD regressions; matrix schema finalize.
  - Confirm Alembic head stays `0017`, replay/codec pair stays `v22`/`v20`, command count stays 43, observer semantic count stays 73, metric family count is 115, and runner schema v48 is the only new accepted schema. Confirm disabled/off runs are byte-identical and no story tokens, record text, or witness payloads enter logs or metrics.
  - Acceptance: no new gate exclusions or suppressed errors; v2 provenance is bounded and monotonic; all-witness-dead survival and source loss are deterministic; no truth field exists; records and retellings stay owner-scoped; analysis is detached and metadata-only; all three families are registered and tested.
  - Logging: record verification outcomes and safe failure codes in the plan log; never paste story tokens, record text, witness payloads, or record bodies.
  - Dependencies: 1–15.

## Verification Notes

Focused suites to add or run during implementation:

- `tests/unit/test_generational_narrative_contracts.py`
- `tests/unit/test_runner_config_v48.py`
- `tests/unit/test_generational_narrative_runtime_carry.py`
- `tests/unit/test_generational_narrative_blank_slate.py`
- `tests/unit/test_narrative_witnesses.py`
- `tests/unit/test_narrative_source_loss.py`
- `tests/unit/test_narrative_retellings.py`
- `tests/unit/test_narrative_records.py`
- `tests/unit/test_narrative_transitions.py`
- `tests/unit/test_narrative_themes.py`
- `tests/unit/test_generational_narrative_loop.py`
- `tests/unit/test_generational_narrative_persistence.py`
- `tests/unit/test_generational_narrative_rows.py`
- `tests/unit/test_generational_narrative_harvest.py`
- `tests/unit/test_generational_narrative_continuity_metrics.py`
- `tests/unit/test_narrative_source_loss_metrics.py`
- `tests/unit/test_narrative_historical_alignment_metrics.py`
- `tests/unit/test_experiment_be.py`
- `tests/unit/test_generational_narrative_overlay.py`
- `tests/unit/test_generational_narrative_route.py`
- `tests/architecture/test_v3_generational_narratives_analysis_only.py`

Required compatibility gates:

- `uv run --frozen --python 3.12.14 pytest`
- `uv run --frozen --python 3.12.14 ruff check src tests`
- `uv run --frozen --python 3.12.14 mypy src tests`
- `uv run --frozen --python 3.12.14 pytest tests/unit/test_compatibility_matrix.py tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py tests/unit/test_alembic_head_pin.py -q`
- `uv run --frozen --python 3.12.14 pytest tests/unit/test_experiment_be.py tests/unit/test_experiment_bd.py tests/unit/test_experiment_bc.py -q`
- Import-linter and architecture isolation checks used by the repository.

Final selector check:

- Commands: **43**
- Observer semantic types: **73**
- Metric families: **112 → 115**
- Runner schema: **v48 only when `generational_narratives` is present**
- Replay / codec: **v22 / v20**
- Alembic head: **0017**
- Experiment: **BE (`generational_narratives@1`)**
- V1/V2/V3 flags-off behavior: **byte-identical**
