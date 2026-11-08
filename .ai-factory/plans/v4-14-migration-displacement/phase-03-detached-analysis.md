# Phase 3: Detached Detection and Metrics

Plan: [index.md](index.md)
Tasks: 11-15
Depends on: Phase 2 / Tasks 4-10

## Objective

Build detached, read-only analysis over committed movement events and exported
owner ledgers: objective movement rows, subjective cause rows, analytical wave
and cluster candidates, integration outcomes, forward-only lineage,
researcher-only alignment, and four appended metric families. The four layers
stay in separate types with a hard leakage guard.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/analysis/regional_population.py` | `RegionalEventRow` 88-127; `QualifiedMigrationRow` 245-252; `fold_regional_history` 292-568; `compute_regional_population` 573-682 | Existing detached movement reconstruction; V4-14 reuses event facts without rewriting the family |
| `src/analysis/regional_migration_metrics.py` | 33-126 | Existing raw/qualified/return-flow metrics; unchanged |
| `src/analysis/regional_destination_beliefs.py` | `RegionalDestinationEvidenceRow` 43-73; `compute_regional_destination_beliefs` 76-190 | Existing owner-belief coverage metric; unchanged |
| `src/analysis/borders_events.py` | physical row extraction and tokenization | Precedent for token-only objective event rows |
| `src/analysis/borders_layers.py` | 28-182; layer separation guard | Precedent for four separated layers and hard failure |
| `src/analysis/borders_detection.py` | overlap/dispute/pattern detection | Precedent for deterministic candidate detection |
| `src/analysis/borders_identity.py` | content-addressed candidates and lineage | Precedent for `mig-` candidates and forward-only lineage |
| `src/analysis/borders_alignment.py` | researcher-only alignment | Precedent for closed alignment labels |
| `src/analysis/borders_metrics.py` | four metric documents | Precedent for four appended families |
| `src/analysis/organized_conflict_events.py` | `ConflictEventRow` 70-100; `conflict_event_rows_from_events` 143-357 | Precedent for hostile/assistance/custody objective rows |
| `src/analysis/organized_conflict_detection.py` | 93-335 | Precedent for closed detection thresholds |
| `src/analysis/specifications.py` | `METRIC_FAMILY_COUNT` 52-53; regional specs 4067-4219; border `_BUILDERS` tail 8354-8357; count check 8382 | Catalog currently 176; V4-14 appends four after the border families |
| `src/analysis/metric_service.py` | `MetricComputationInputs` 218-345; regional block 2555-2568; border block 2141-2250 | Exact integration point for four new families |
| `src/experiments/composition.py` | `regional_context_from_run` 586-665; `regional_population_rows_from_events` 668-793; border harvest 918-927 | Exact harvest/composition integration point |
| `src/experiments/borders_harvest.py` | `BordersHarvest` 52; `build_completed_run_borders_harvest` 66-138 | Precedent for completed-run harvest |
| `tests/unit/test_regional_demographics.py` | 118-375, 472-635 | Existing migration conservation and metric cases |
| `tests/unit/test_borders_layers.py` | 63-131 | Leakage-guard test shape |
| `tests/unit/test_borders_catalog.py` | catalog count and first-family stability | Pin-sweep test shape |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/analysis/migration_displacement_events.py` | create | Objective movement rows from committed events |
| `src/analysis/migration_displacement_rows.py` | create | Harvest row contracts and owner-row ingestion |
| `src/analysis/migration_displacement_layers.py` | create | Four separated layers and hard leakage guard |
| `src/analysis/migration_displacement_detection.py` | create | Wave, displacement, cluster, and integration detection |
| `src/analysis/migration_displacement_identity.py` | create | `mig-` candidates, lineage, read-only joins |
| `src/analysis/migration_displacement_alignment.py` | create | Researcher-only alignment |
| `src/analysis/migration_displacement_metrics.py` | create | Four metric documents |
| `src/analysis/specifications.py` | modify | Append four families; `METRIC_FAMILY_COUNT = 180` |
| `src/analysis/metric_service.py` | modify | Add harvest input fields and compute blocks |
| `src/experiments/composition.py` | modify | Harvest completed-run rows and attach them |
| `tests/unit/test_migration_displacement_events.py` | create | Objective movement extraction |
| `tests/unit/test_migration_displacement_layers.py` | create | Four-layer separation |
| `tests/unit/test_migration_displacement_detection.py` | create | Wave/displacement/cluster/outcome detection |
| `tests/unit/test_migration_displacement_identity.py` | create | Candidates, lineage, joins |
| `tests/unit/test_migration_displacement_metrics.py` | create | Four metric documents |
| `tests/unit/test_migration_displacement_catalog.py` | create | Catalog 176 -> 180 and first-176 stability |

## Task 11: Harvest objective migration movement rows from committed events

### Intent

Turn committed movement facts into token-only objective rows without reading an
owner's cause, intent, or belief. These rows are the only objective layer and
never carry a cause or classification.

### Implementation Steps

1. Create `src/analysis/migration_displacement_events.py` with:
   - `MIGRATION_MOVEMENT_PREFIX = "mig-move-"`;
   - `MigrationMovementKind` closed to `move`, `transport`, `flee`, `journey`;
   - `MigrationArrivalStatus` closed to `arrived`, `timeout`, `dead`, `pending`,
     `unknown`;
   - `MigrationMovementRow`:
     `participant_token`, `origin_token`, `destination_token`,
     `route_tokens`, `start_tick`, `end_tick`, `relocation_kind`,
     `group_size`, `arrival_status`, `coverage`.
   - `MigrationIntegrationEvidenceRow`:
     `participant_token`, `destination_token`, `domain`, `evidence_count`,
     `first_tick`, `last_tick`, `coverage`.
2. Implement `migration_movement_rows_from_events(events, *, run_id,
   input_revision, region_topology=None, max_pairs=4096)`:
   - read `Moved`, `Transported`, `Fled`, `JourneyStarted`, `JourneyArrived`,
     `JourneyEnded`, `ContactRecorded`, `LifecycleStageChanged`,
     `PopulationEntryRecorded`, `Died`;
   - pair `JourneyStarted` with `JourneyArrived` or `JourneyEnded` by
     participant and journey identity; emit one row per completed journey;
   - for non-regional relocation events, emit one row per event;
   - a multi-hop journey is emitted as one objective row per hop; analysis may
     chain consecutive rows for the same participant by tick order when it needs
     an observed multi-hop route;
   - derive origin/destination locations from the event; derive region tokens
     only from the supplied `regions_migration` topology;
   - set `group_size` from the participant set in the event, bounded to 8;
   - set `coverage=complete` only when the run boundary and event high-water are
     complete; otherwise `partial` or `missing`.
3. Deduplicate rows by `(participant_token, origin_token, destination_token,
   start_tick, relocation_kind)`; sort by `(start_tick, participant_token,
   destination_token)`.
4. Implement `migration_integration_rows_from_events(events, *, run_id,
   input_revision, max_pairs=4096)`:
   - read `NeedsApplied`, `ExposureApplied`, `ExchangeCompleted`,
     `PublicGoodBenefit`, `ProjectContributed`, `Given`, `Taken`, `Attacked`,
     `ContactRecorded`, `Talked`, `Asked`, `Told`, and `KinshipEdgeRecorded`;
   - count evidence per `(participant_token, destination_token, domain)` for
     the closed domains `residence`, `needs`, `resource_access`,
     `organization_participation`, `institution_participation`,
     `relationships`, `conflict_status`;
   - set `first_tick`/`last_tick` from the contributing events;
   - never infer participation or access from silence;
   - for `organization_participation` and `institution_participation`, count
     only already-exported, read-only participation rows; if none exist, leave
     the domain `missing` rather than inferring it from unrelated events;
   - sort by `(participant_token, destination_token, domain)`.
5. Never read `Observation`, a ledger, a cause, a frame, or a command. This
   module imports only `world.events` public types and analysis contracts.
6. Tokenize every identity with SHA-256 and a stable per-run salt; no raw
   `AgentId`, `EntityId`, or location label appears in a row.
7. Add `__all__` entries.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class MigrationMovementRow:
    participant_token: str
    origin_token: str
    destination_token: str
    route_tokens: tuple[str, ...]
    start_tick: int
    end_tick: int
    relocation_kind: str
    group_size: int
    arrival_status: str
    coverage: str
```

- Objective rows have no `cause_kind`, `classification`, `wave_token`, or
  `owner_token`.
- A pending journey is `arrival_status=pending`; a timed-out journey is
  `timeout`; a dead participant is `dead`.
- No row is invented from silence or from a region label alone.
- Existing `regional_population@1` and `regional_migration@1` inputs are not
  modified.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — track origin, route, destination, waves.
- Source: `.ai-factory/ARCHITECTURE.md` — detached analysis reads committed
  events only.
- Source: `src/analysis/regional_population.py` 292-568; `src/world/events.py`
  392-474.
- Supported combinations: move; transport; flee; journey arrival; journey
  timeout; journey death; pending journey; partial coverage; duplicate event;
  each is tested.

### Error Handling and Logging

- A malformed event is skipped with `WARN migration_movement_event_skipped
  reason_code=%s` and a count.
- An unknown relocation kind is `unknown`, never guessed.
- Log `DEBUG migration_movement_rows events=%s rows=%s complete=%s`; never log
  raw ids, locations, or participants.

### Tests

- `tests/unit/test_migration_displacement_events.py`
  - `test_move_transport_and_flee_become_objective_rows`
  - `test_journey_start_arrival_pairs_once`
  - `test_journey_timeout_and_death_statuses`
  - `test_pending_journey_is_not_an_arrival`
  - `test_partial_boundary_is_explicit`
  - `test_rows_are_sorted_and_deduplicated`
  - `test_rows_contain_no_cause_or_owner_token`
  - `test_integration_evidence_counts_closed_domains`
  - `test_integration_evidence_never_infers_from_silence`
  - `test_tokenization_is_stable`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_events.py -q`
- Expected: all pass.

### Acceptance Criteria

- Objective rows derive only from committed events.
- Pairing and sorting are deterministic; duplicates do not inflate counts.
- No cause, owner, or analytical field appears in an objective row.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_events.py -q`
- `rg -n "cause_kind|owner_token|classification|wave_token" src/analysis/migration_displacement_events.py` — expected: no matches in row fields.
- Expected: pass.

## Task 12: Harvest owner migration rows and keep four layers separate

### Intent

Ingest the token-only owner export and project four distinct layers. A leak
between objective movement, subjective cause, analytical wave, and integration
outcome is a hard failure, not a warning.

### Implementation Steps

1. Create `src/analysis/migration_displacement_rows.py` with:
   - `MigrationCauseRow`: `owner_token`, `cause_token`, `cause_kind`,
     `source_kind`, `anchor_token`, `lineage_refs`, `confidence`, `tick`,
     `status`.
   - `MigrationRouteRow`: `owner_token`, `route_token`, `origin_token`,
     `destination_token`, `route_tokens`, `observed_duration_ticks`,
     `fatigue_cost`, `basis`, `status`, `first_tick`, `last_tick`.
   - `MigrationClusterRow`: `cluster_token`, `member_tokens`, `basis_counts`
     (sorted `(basis,count)` tuples), `coverage`, `first_tick`, `last_tick`.
   - `MigrationWaveRow`: `wave_token`, `origin_token`, `destination_token`,
     `participant_tokens`, `route_tokens`, `start_tick`, `end_tick`,
     `cause_support_counts` (sorted `(cause_kind,count)` tuples),
     `displacement_classification`, `displacement_bases`, `independent_cause_count`,
     `cluster_tokens`, `coverage`.
   - `MigrationOutcomeRow`: `outcome_token`, `participant_token`,
     `destination_token`, `residence_ticks`, `access_evidence_count`,
     `participation_evidence_count`, `relationship_evidence_count`,
     `conflict_evidence_count`, `classification`, `coverage`, `censored`.
   - `MigrationLineageRow`: `candidate_token`, `previous_token`, `relation`,
     `first_tick`, `last_tick`.
   - `MigrationAlignmentRow`: `owner_token`, `candidate_token`, `alignment`,
     `basis`.
   - `MigrationDisplacementHarvestRows`: movements, routes, causes, clusters,
     waves, outcomes, lineage, alignment, coverage.
2. Add `harvest_migration_displacement_rows(owner_rows, movements,
   integration_evidence, *, kinship_pairs=(), organization_pairs=(),
   communication_pairs=(), previous_candidates=(), policy)`:
   - if `owner_rows` is already a `MigrationDisplacementHarvestRows` (or an
     equivalent normalized harvest object), return it through the same
     duplicate-owner check and deterministic ordering without re-projecting
     raw ledgers (collector → metric-service idempotence; V4-09 lesson);
   - otherwise validate owner export tokens and families;
   - keep route/cause/cluster rows subjective;
   - source `kinship_pairs` only from `KinshipEdgeRecorded`;
   - source `organization_pairs` only from already-exported, read-only
     organization membership rows (`org-`), never by importing or reading a
     peer cognition ledger;
   - source `communication_pairs` only from committed `Talked`/`Asked`/`Told`
     events;
   - merge optional already-exported organization/institution participation
     rows into `integration_evidence`; absent rows stay `missing`;
   - import detection and alignment lazily inside the function to avoid a
     module cycle;
   - run Task 13 detection for waves and outcomes using
     `integration_evidence`;
   - run Task 14 lineage and alignment;
   - return the complete harvest with `coverage` `complete`, `partial`, or
     `missing`.
3. Create `src/analysis/migration_displacement_layers.py`:
   - `MigrationLayer` enum: `objective_movement`, `subjective_cause`,
     `analytical_wave`, `integration_outcome`.
   - Four layer container types:
     `ObjectiveMovementLayer`, `SubjectiveCauseLayer`,
     `AnalyticalWaveLayer`, `IntegrationOutcomeLayer`.
   - `project_migration_layers(rows) -> MigrationLayers`.
   - `assert_migration_layer_separation(layers)`:
     - objective rows reject `cause_kind`, `owner_token`, `classification`,
       `wave_token`;
     - subjective rows reject `wave_token`, `classification`,
       `candidate_token`;
     - analytical rows reject `raw_owner_id`, `raw_agent_id`,
       `raw_entity_id`, `refugee`, `forced`, `score`, `composite`,
       `wellbeing`, `assimilation`;
     - integration rows reject `cause_kind`, `wave_token`, `score`,
       `wellbeing`, `assimilation`.
   - A violation raises `MigrationLayerLeakError`.
4. Ensure analysis modules never import `agents.cognition`,
   `simulation.runner`, `experiments`, `api`, `persistence`, or `observer`.
5. Add `__all__` entries.

### Required Interfaces and Contracts

- Four layers are separate dataclasses and separate tuples; no row type is
  reused across layers.
- Every token is lowercase `[a-z0-9][a-z0-9-]{0,63}`.
- A subjective row may carry an owner token, but no analytical classification.
- An analytical row may carry candidate tokens, but no raw identity.
- Missing owner export is `coverage=missing`; it is never replaced with zeros or
  invented rows.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — cause evidence and integration outcomes are tracked
  separately from movement.
- Source: `.ai-factory/ARCHITECTURE.md` — Key Principle 1; analysis isolation.
- Source: `src/analysis/borders_layers.py` 28-182.
- Supported combinations: complete export; partial export; missing export;
  objective-only; subjective-only; analytical-only; leak in each layer; each is
  tested.

### Error Handling and Logging

- A leak raises `MigrationLayerLeakError("<layer>:<field>")`.
- A missing export logs `WARN migration_harvest_missing_owner_rows` and sets
  coverage missing.
- Log `DEBUG migration_layers objective=%s subjective=%s analytical=%s
  integration=%s`; never log row contents.

### Tests

- `tests/unit/test_migration_displacement_layers.py`
  - `test_four_layers_are_distinct_types`
  - `test_objective_layer_rejects_cause_and_owner_fields`
  - `test_subjective_layer_rejects_wave_and_classification_fields`
  - `test_analytical_layer_rejects_raw_identity_and_score_fields`
  - `test_integration_layer_rejects_cause_and_score_fields`
  - `test_missing_owner_export_is_missing_coverage`
  - `test_already_normalized_harvest_is_accepted_idempotently`
  - `test_analysis_imports_do_not_reach_cognition_or_runtime`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_layers.py -q`
- Expected: all pass.

### Acceptance Criteria

- The four layers are separate and a leak fails hard.
- Missing owner export is explicit, never invented.
- Analysis imports obey the dependency rules.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_layers.py -q`
- `uv run --frozen --python 3.12.14 lint-imports`
- Expected: pass.

## Task 13: Detect migration waves, displacement-like classification, social clusters, and integration outcomes

### Intent

Group independent committed movements into deterministic analytical wave
candidates, classify displacement-like migration from independent causal
evidence, detect social clusters, and classify integration outcomes. No wave is
a world object, and no participant shares knowledge implicitly.

### Implementation Steps

1. Create `src/analysis/migration_displacement_detection.py`.
2. Implement `detect_migration_waves(movements, causes, clusters, policy)`:
   - sort movements by `(destination_token, start_tick, participant_token)`;
   - slide a window of `wave_window_ticks`, splitting when the gap between
     consecutive movements exceeds `max_wave_gap_ticks`;
   - require `>= min_wave_participants` distinct participants,
     `>= min_wave_distinct_origins` distinct origins, and
     `>= min_wave_route_overlap` shared route token or origin token;
   - assign `wave_token = analysis_migration_candidate_id("wave", material)`
     where material is the canonical tuple of destination, sorted participants,
     sorted origins, first tick, and **ordered** route sequences (preserve hop
     order; do not sort tokens inside a route, or opposite paths collide);
   - sort candidate participants, origins, and clusters for presentation; keep
     each route sequence ordered;
   - never merge two windows that do not satisfy the gap rule.
3. Implement `classify_displacement(wave, causes, policy)`:
   - select cause rows whose `owner_token` is a wave participant and whose
     `tick` is within `cause_window_ticks` of the wave window;
   - deduplicate by `(cause_kind, anchor_token, any lineage_ref)`; suppress
     same-root testimony when any `lineage_refs` entry overlaps;
   - count independent causes;
   - map each independent cause row to **exactly one** base class — never both
     a displacement base and an opportunity base:
     - displacement bases:
       `immediate_threat` from `conflict` with an attack/flee/death anchor;
       `resource_deprivation` from `resource_scarcity` with a need/depletion
       anchor; `environmental_hazard` from `environmental_hazard`;
       `coercion` from `conflict` with a threat/coercion anchor;
       `route_denial` from `conflict` or `border_belief` with a blocked/denied
       route anchor; `institutional_exclusion` from `institution` with a rule/
       office/participation denial anchor;
     - opportunity bases:
       `opportunity` from `opportunity`;
       `social_network` from `social_network`;
       `institution` from `institution` **without** an exclusion/denial anchor;
     - if a row could match both, prefer the displacement base and do not also
       count it as opportunity;
   - classify:
     - `displacement_like` when at least one displacement base and no
       opportunity base;
     - `mixed` when at least one displacement base and at least one
       opportunity base;
     - `not_displacement_like` when no displacement base and at least one
       opportunity base;
     - `unknown` when there are no usable cause rows or only `unknown`.
   - never produce a `refugee`, `asylum`, `forced`, or `displaced` label.
4. Implement `detect_migration_clusters(movements, kinship_pairs,
   organization_pairs, communication_pairs, policy)`:
   - union participants with shared objective kinship, organization membership,
     communication, or co-movement within `cluster_window_ticks`;
   - require `>= min_cluster_members`;
   - assign `cluster_token = analysis_migration_candidate_id("cluster", material)`;
   - record sorted `(basis, count)` tuples and coverage;
   - never create an `org-`/`msoc-` identity.
5. Implement `classify_integration_outcomes(movements, integration_evidence,
   policy)`:
   - for each wave participant and destination, find the arrival tick and
     post-arrival rows within `integration_window_ticks`; compute
     `residence_ticks` as the next departure tick minus the arrival tick, or the
     run end minus the arrival tick when no departure is observed and mark it
     `censored` if the run ends before the full window;
   - `returned` when a later movement returns to the origin;
   - `onward` when a later movement goes to a different destination;
   - `settled` when residence ticks `>= min_residence_ticks` and at least one
     access/participation/relationship evidence count is positive;
   - `transient` when residence is shorter or no evidence exists;
   - `unknown` when destination/residence evidence is missing;
   - set `censored=True` when the run ends before the window completes;
   - never compute a wellbeing or assimilation score.
6. All outputs are sorted by candidate token and are pure functions of the
   inputs.

### Required Interfaces and Contracts

```python
DISPLACEMENT_CLASSIFICATIONS: Final[frozenset[str]] = frozenset(
    {"not_displacement_like", "displacement_like", "mixed", "unknown"}
)
DISPLACEMENT_BASES: Final[frozenset[str]] = frozenset(
    {
        "immediate_threat",
        "resource_deprivation",
        "environmental_hazard",
        "coercion",
        "route_denial",
        "institutional_exclusion",
        "unknown",
    }
)
INTEGRATION_CLASSIFICATIONS: Final[frozenset[str]] = frozenset(
    {"settled", "transient", "returned", "onward", "unknown"}
)
```

- A wave requires independent committed movements; communication is optional.
- A single participant is never a wave.
- A single cause is never a wave.
- Same-root testimony is counted once.
- No classification is a truth claim; it is a researcher-only label with
  coverage.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — waves without telepathy; displacement-like
  classification from causal evidence; family/social clusters; integration
  outcomes.
- Source: `.ai-factory/ARCHITECTURE.md` — analysis is detached and read-only.
- Source: `src/analysis/borders_detection.py`; `src/analysis/organized_conflict_detection.py`.
- Supported combinations: 1 participant; 2 participants; same origin; different
  origins; gap too large; displacement-only; mixed; opportunity-only; no cause;
  return; onward; settled; transient; censored; each is tested.

### Error Handling and Logging

- Invalid thresholds raise `ValueError("migration_detection: <code>")`.
- Missing cause rows produce `unknown`, never an invented cause.
- Log `DEBUG migration_waves movements=%s waves=%s displacement_like=%s mixed=%s
  unknown=%s` with counts only.
- Never log participant tokens, origins, destinations, routes, or cause anchors.

### Tests

- `tests/unit/test_migration_displacement_detection.py`
  - `test_one_participant_is_not_a_wave`
  - `test_two_independent_participants_form_a_wave`
  - `test_same_destination_and_shared_origin_is_required`
  - `test_window_gap_splits_waves`
  - `test_opposite_ordered_routes_do_not_share_wave_identity`
  - `test_displacement_like_requires_independent_displacement_evidence`
  - `test_institution_exclusion_and_opportunity_are_mutually_exclusive_per_row`
  - `test_mixed_and_not_displacement_like_are_distinct`
  - `test_unknown_when_no_cause_evidence`
  - `test_same_root_testimony_counts_once`
  - `test_cluster_requires_two_members_and_a_basis`
  - `test_integration_returned_onward_settled_transient_and_censored`
  - `test_no_refugee_or_score_label_is_emitted`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_detection.py -q`
- Expected: all pass.

### Acceptance Criteria

- Wave, displacement, cluster, and outcome outputs are deterministic and sorted.
- No cause is invented from movement or silence.
- No refugee, forced, wellbeing, assimilation, or score label exists.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_detection.py -q`
- `rg -n "refugee|asylum|forced|wellbeing|assimilation|score" src/analysis/migration_displacement_detection.py` — expected: only forbidden-field guards, no emitted labels.
- Expected: pass.

## Task 14: Add migration lineage, read-only identity joins, and researcher-only alignment

### Intent

Give analytical candidates stable, forward-only lineage without minting or
mutating `org-`/`msoc-` identities, and classify owner-cause alignment for
researchers only. Alignment never reaches cognition, prompts, memory, world
state, observer semantics, or stop selectors.

### Implementation Steps

1. Create `src/analysis/migration_displacement_identity.py`:
   - `migration_candidate_row(kind, candidate_token, ...)` producing a
     `MigrationCandidateRow` with `candidate_token`, `kind`, `status`,
     `first_tick`, `last_tick`, `member_count`, `origin_token`,
     `destination_token`, `classification`, `coverage`.
   - `link_migration_lineage(previous, current, policy)`:
     - content-addressed candidate tokens;
     - `continued` when member overlap is `>= 0.5` and destination matches;
     - `transformed` when member overlap is `>= 0.5` and destination changes;
     - `split` when one previous candidate maps to two or more current
       candidates;
     - `merge` when two or more previous candidates map to one current
       candidate;
     - `dissolved` when a previous candidate has no successor;
     - `emerged` when a current candidate has no predecessor;
     - sort by `(first_tick, candidate_token, previous_token)`.
   - `join_read_only_identities(candidates, org_tokens, msoc_tokens)`:
     - attach matching `org-`/`msoc-` tokens by member-token overlap;
     - never create, rename, split, merge, or dissolve those identities.
2. Create `src/analysis/migration_displacement_alignment.py`:
   - `align_migration_interpretations(causes, waves, outcomes)`:
     - `consistent` when an owner cause kind maps to the analytical
       displacement basis or outcome class;
     - `inconsistent` only when positive contradictory evidence exists;
     - `unresolved` when evidence is missing or coverage is partial;
     - `not_applicable` when the owner is not a wave participant or there is no
       candidate;
     - sort by `(owner_token, candidate_token)`.
3. Add a `MIGRATION_ALIGNMENTS` frozenset with exactly the four labels.
4. Add `MIGRATION_CANDIDATE_PREFIX = "mig-"`; candidate ids are
   content-addressed and never raw hashes of unordered data.
5. Ensure the modules import only analysis contracts and public world/simulation
   facts. They never import `agents.cognition` or `experiments`.

### Required Interfaces and Contracts

```python
MIGRATION_ALIGNMENTS: Final[frozenset[str]] = frozenset(
    {"consistent", "unresolved", "inconsistent", "not_applicable"}
)
MIGRATION_CANDIDATE_PREFIX: Final[str] = "mig-"
```

- Lineage is forward-only; a previous candidate is never rewritten.
- `org-`/`msoc-` joins are read-only; no identity is minted or changed.
- Missing evidence is `unresolved`, never `inconsistent`.
- Alignment is researcher-only and never appears in a cognition input.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — research analytics classify from causal evidence.
- Source: `.ai-factory/ARCHITECTURE.md` — "analysis is read-only"; V4-08/V4-11
  alignment precedent.
- Supported combinations: continued; transformed; split; merge; dissolved;
  emerged; missing org/msoc; consistent; unresolved; inconsistent;
  not_applicable; each is tested.

### Error Handling and Logging

- An invalid candidate token raises
  `ValueError("migration_identity: candidate_token")`.
- Missing evidence logs `DEBUG migration_alignment_unresolved count=%s`; never
  logs owner or candidate tokens.
- An `org-`/`msoc-` mutation attempt raises
  `ValueError("migration_identity: read_only_identity")`.

### Tests

- `tests/unit/test_migration_displacement_identity.py`
  - `test_candidate_tokens_are_content_addressed`
  - `test_lineage_continued_transformed_split_merge_dissolved_emerged`
  - `test_lineage_is_forward_only_and_sorted`
  - `test_org_and_msoc_joins_are_read_only`
  - `test_no_org_or_msoc_identity_is_minted`
  - `test_alignment_missing_evidence_is_unresolved`
  - `test_inconsistency_requires_positive_contradiction`
  - `test_alignment_does_not_reach_cognition_inputs`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_identity.py -q`
- Expected: all pass.

### Acceptance Criteria

- `mig-` candidates are stable and forward-only.
- `org-`/`msoc-` identities are only read.
- Alignment is researcher-only and missing evidence is unresolved.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_identity.py -q`
- `rg -n "org-|msoc-" src/analysis/migration_displacement_identity.py` — expected: only read-only join handling.
- Expected: pass.

## Task 15: Add four metric families and raise the catalog to 180

### Intent

Append four analysis-only families that describe wave structure, cause evidence,
cluster cohesion, and integration outcomes with counts, durations, ratios, and
denominators. No composite migration, displacement, integration, wellbeing, or
assimilation score exists.

### Implementation Steps

1. Create `src/analysis/migration_displacement_metrics.py` with:
   - `compute_migration_wave_structure(rows, *, run_id, input_revision)`
   - `compute_migration_cause_evidence(rows, *, run_id, input_revision)`
   - `compute_migration_cluster_cohesion(rows, *, run_id, input_revision)`
   - `compute_migration_integration_outcome(rows, *, run_id, input_revision)`
2. Append four specs to `src/analysis/specifications.py` after the current
   final family:
   - `migration_wave_structure@1`
   - `migration_cause_evidence@1`
   - `migration_cluster_cohesion@1`
   - `migration_integration_outcome@1`
   Set `METRIC_FAMILY_COUNT = 180`.
3. Define exact value keys:
   - `migration_wave_structure@1`:
     `wave_count`, `participant_count`, `distinct_origin_count`,
     `distinct_destination_count`, `wave_participant_mean`,
     `wave_participant_max`, `route_length_counts`, `wave_duration_ticks`,
     `return_count`, `onward_count`, `same_origin_share`,
     `same_destination_share`, `cluster_overlap_count`, `coverage_complete`,
     `coverage_partial`, `coverage_missing`.
   - `migration_cause_evidence@1`:
     `cause_count:<kind>`, `source_count:<kind>`, `owner_coverage_ratio`,
     `wave_with_cause_count`, `wave_without_cause_count`,
     `contradicted_cause_count`, `unresolved_anchor_count`,
     `same_root_suppressed_count`, `displacement_like_count`, `mixed_count`,
     `not_displacement_like_count`, `unknown_count`,
     `independent_cause_mean`.
   - `migration_cluster_cohesion@1`:
     `cluster_count`, `cluster_size:<bucket>`, `co_movement_pair_count`,
     `kinship_supported_pair_count`, `organization_supported_pair_count`,
     `communication_supported_pair_count`, `relationship_supported_pair_count`,
     `independent_support_ratio`, `cluster_wave_overlap_count`,
     `unknown_cluster_count`, `coverage_complete`, `coverage_partial`.
   - `migration_integration_outcome@1`:
     `outcome:<label>`, `residence_ticks:<bucket>`,
     `access_evidence_count`, `participation_evidence_count`,
     `relationship_evidence_count`, `conflict_evidence_count`,
     `censored_count`, `unknown_count`, `complete_coverage_count`,
     `partial_coverage_count`, `missing_coverage_count`.
4. Add `migration_displacement_rows: object | None = None` and optional
   `migration_displacement_*` row fields to `MetricComputationInputs` in
   `src/analysis/metric_service.py`.
5. Add a compute block in `compute_metric_documents` guarded by
   `inputs.migration_displacement_rows is not None`, mirroring the border block.
   Call `harvest_migration_displacement_rows` on the attached object so an
   already-normalized harvest from the collector is accepted idempotently;
   never import `experiments` or `agents.cognition`.
6. In `src/experiments/composition.py`, harvest completed-run rows with
   `build_completed_run_migration_displacement_harvest` and attach
   `migration_displacement_rows=` to the inputs. Do this only when the feature
   is active; otherwise leave it `None`. The real completed-run path must
   exercise collector → `metric_service` without a second raw-ledger harvest.
7. Keep the first 176 specs byte-identical: ids, order, versions, and value
   keys. Only append after `_spec_border_control_alignment` in `_BUILDERS`
   (currently lines 8354-8357; count check near 8382).
8. Add catalog tests that assert 180, the four names at positions 177-180, and
   the first 176 unchanged.

### Required Interfaces and Contracts

- All four metrics are analysis-only and never feed cognition, prompts, memory,
  world state, observer semantics, or stop selectors.
- All ratios are quantized to six decimals; all counts are integers.
- Missing input emits an empty/`unknown` document with explicit coverage, not a
  fabricated zero-cause result.
- No metric key contains `score`, `refugee`, `forced`, `wellbeing`, or
  `assimilation`.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — research analytics and four tracked dimensions.
- Source: `src/analysis/specifications.py` 52-53, `_BUILDERS` tail 8354-8357,
  count check 8382; V4-13 catalog precedent; V4-09 double-harvest prevention.
- Supported combinations: empty harvest; one wave; multiple waves; no causes;
  mixed causes; no clusters; complete/partial/missing coverage; already-
  normalized harvest passed through collector then metric service; each is
  tested.

### Error Handling and Logging

- A malformed harvest raises `ValueError("migration_metrics: <code>")`.
- Missing input logs `DEBUG migration_metrics_disabled` and emits no fabricated
  rows.
- Log `INFO migration_metrics_emitted families=4`; never log row contents.

### Tests

- `tests/unit/test_migration_displacement_metrics.py`
  - `test_wave_structure_counts_and_ratios`
  - `test_cause_evidence_counts_and_coverage`
  - `test_cluster_cohesion_counts_independent_support`
  - `test_integration_outcome_counts_and_censoring`
  - `test_empty_harvest_is_explicit_not_zero_cause`
  - `test_no_composite_or_refugee_value_key_exists`
  - `test_collector_then_metric_service_does_not_double_harvest`
- `tests/unit/test_migration_displacement_catalog.py`
  - `test_catalog_count_is_180`
  - `test_four_migration_families_are_last`
  - `test_first_176_ids_order_versions_and_keys_are_unchanged`
  - `test_no_current_pin_asserts_176`
- Commands:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_metrics.py tests/unit/test_migration_displacement_catalog.py tests/unit/test_metric_specifications.py -q`
- Expected: all pass.

### Acceptance Criteria

- The catalog is exactly 180 with four appended families.
- The first 176 are unchanged.
- All four documents emit counts, durations, ratios, labels, and coverage only.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_metrics.py tests/unit/test_migration_displacement_catalog.py -q`
- `rg -n "METRIC_FAMILY_COUNT|176|180|_spec_border_control_alignment" src/analysis/specifications.py tests/unit/test_metric_specifications.py` — expected: 180 current; append after border tail; historical statements intact.
- Expected: pass.

## Phase Risks and Mitigations

- Risk: objective movement is contaminated with subjective causes.
  Mitigation: Task 11 row type has no cause/owner field; Task 12 leakage guard
  rejects it.
- Risk: a wave implies shared knowledge.
  Mitigation: Task 13 groups independent movements; Task 23 asserts no shared
  ledger and no cognition import.
- Risk: displacement classification becomes a refugee category.
  Mitigation: closed labels exclude `refugee`/`forced`; Task 23 scans forbidden
  names; docs state it is researcher-only.
- Risk: integration outcomes become a wellbeing score.
  Mitigation: Task 13 emits labels/counts/coverage; Task 15 forbids score keys.
- Risk: the catalog append reorders or rewrites existing families.
  Mitigation: Task 15 appends only and tests the first 176 digests.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
