# Phase 3: Detached Detection and Metrics

Plan: [index.md](index.md)
Tasks: 11-15
Depends on: Phase 2

## Objective

Build the detached research pipeline that detects sustained organized conflict
from committed event patterns, separates individual violence from coordinated and
persistent inter-group conflict, retains multiple owner interpretations, joins
existing analytical identities read-only, and appends four metric families to
the catalog (168 -> 172).

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/analysis/diplomacy_contract.py` | tokens 188-226; candidate/edge IDs 229-259; forbidden fields 73-96 | Token and ID pattern; conflict must add its own namespaced prefixes |
| `src/analysis/diplomacy_rows.py` | `DiplomacyHarvestRows` 396-414; harvest 476-870 | Owner-row harvesting and tokenization pattern |
| `src/analysis/diplomacy_objective.py` | `_ATTACK_KINDS` 18; anchor rows 21-72; windows 75-100 | Objective event join pattern; current attack-class join is incomplete, do not copy it |
| `src/analysis/diplomacy_detection.py` | `detect_diplomacy_candidates` | Candidate detection pattern |
| `src/analysis/diplomacy_identity.py` | identity 142-200; lineage 203-263; joins 288-349 | Stable candidate identity, forward-only lineage, read-only joins |
| `src/analysis/diplomacy_layers.py` | layers 35-65; guard 79-111; projection 114-221 | Three-layer separation and hard leakage guard |
| `src/analysis/diplomacy_metrics.py` | `_document` 56-125; computes 135-518 | Metric document assembly and exact value keys |
| `src/analysis/specifications.py` | count 53; enum tail 238-245; builders 7384-7814; `_BUILDERS` 7978-7986; validation 8007-8032 | Catalog append point and count guard |
| `src/analysis/metric_service.py` | inputs 321-324; diplomacy block 1885-2029 | Metric-service integration and the two-path divergence to avoid |
| `src/world/events.py` | `Attacked` 821-842; `Fled` 845-867; `Died` 968-983; `Helped` 744-763; `Taken`/`Given` 580-634; `PublicGoodOpposed` 2728-2752; `Moved` 371-388; journeys 391-472 | The complete objective event vocabulary available without new events |
| `src/analysis/group_formation_metrics.py` | assistance metrics 42, 268 | Existing cooperation metric names to avoid colliding with |
| `tests/unit/test_diplomacy_layers.py` | guard cases 84-120 | Layer-leak tests to mirror |
| `tests/unit/test_diplomacy_identity.py` | stable IDs 37-70; joins 73-96; no minting 100+ | Identity tests to mirror |
| `tests/unit/test_diplomacy_metrics.py` | value keys 122-149; assembly 160-175 | Metric tests to mirror |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/analysis/organized_conflict_events.py` | create | Committed-event rows, actor/target/location tokens, windows |
| `src/analysis/organized_conflict_rows.py` | create | Owner ledger harvest and `OrganizedConflictHarvestRows` |
| `src/analysis/organized_conflict_detection.py` | create | Co-participation graph, episode candidates, three-way classification |
| `src/analysis/organized_conflict_identity.py` | create | `oc-` candidates, `oc-edge-` lineage, read-only `org-`/`msoc-` joins |
| `src/analysis/organized_conflict_layers.py` | create | Three-layer rows, projection, leakage guard |
| `src/analysis/organized_conflict_alignment.py` | create | Researcher-only interpretation alignment and summary |
| `src/analysis/organized_conflict_metrics.py` | create | Four metric computes and documents |
| `src/analysis/specifications.py` | modify | Four enum members, builders, `_BUILDERS`, count 172 |
| `src/analysis/metric_service.py` | modify | Inputs and assembly block |
| `src/experiments/collectors.py` | modify | Completed-run metric-input bridge for conflict rows/alignment |
| `tests/unit/test_organized_conflict_collectors.py` | create | Completed-run assembly emits all four families |
| `src/analysis/__init__.py` | modify | Public facade exports |
| `tests/unit/test_organized_conflict_events.py` | create | Event joins and windows |
| `tests/unit/test_organized_conflict_detection.py` | create | Three classifications and thresholds |
| `tests/unit/test_organized_conflict_identity.py` | create | Stable IDs, lineage, read-only joins |
| `tests/unit/test_organized_conflict_layers.py` | create | Layer separation and leakage |
| `tests/unit/test_organized_conflict_alignment.py` | create | Alignment and disagreement |
| `tests/unit/test_organized_conflict_metrics.py` | create | Exact value keys and assembly |
| `tests/unit/test_organized_conflict_catalog.py` | create | 172, four families last, first 168 unchanged |

## Task 11: Harvest objective conflict rows from committed events

### Intent

Convert existing committed events into token-only objective rows. Detection must
never read owner claims or world state.

### Implementation Steps

1. Create `src/analysis/organized_conflict_events.py`.
2. Define `ConflictEventRow` frozen dataclass:
   `tick`, `sequence`, `event_class`, `actor_token`, `other_token`,
   `success`, `magnitude`, `source_event_kind`, `location_token`,
   `region_token`.
3. Define `conflict_agent_token(agent_id)` and
   `conflict_location_token(entity_id)` using SHA-256 over a namespaced domain
   (`palimpsest.organized_conflict.agent.v1`,
   `palimpsest.organized_conflict.location.v1`) and 16 hex characters. Region
   anchors remain `region`-prefixed opaque anchors, never raw ids.
4. Implement `conflict_event_rows_from_events(events)` mapping:
   - `Attacked` -> `attack`, actor `event.actor_id`, other `target_id`,
     `success=hit`, `magnitude=damage`.
   - `Fled` -> `retreat`, actor `event.actor_id`, other `threat_id`,
     `success`, location `destination_id`.
   - `Died` with `death_cause == ATTACK` -> `death`, actor absent, other
     `body_id`, magnitude `1`.
   - `Helped` -> `assistance`, actor helper, other target, `magnitude` health
     delta.
   - `Fed`/`Transported` -> `assistance`.
   - `Taken` -> `custody_capture`, actor taker, other item, location.
   - `TakenFromCorpse` -> `custody_capture` with corpse anchor.
   - `Given` -> `custody_transfer`, actor giver, other recipient.
   - `PublicGoodOpposed` -> `structure_opposition`, actor, other project,
     `magnitude=integrity_millis`.
   - `Moved` -> `movement`, actor, location destination.
   - `JourneyStarted`/`JourneyArrived` -> `co_movement`, actor absent,
     `public_facts["participant_count"]`, participant tokens from
     `details.participant_body_ids`, and endpoint tokens.
   - `ContactRecorded` -> `contact`, co-presence only, never conflict.
   - Derive `route_denial` evidence rows only in Task 13 from a failed `retreat`
     with a threat plus a hostile `attack` at the same origin/destination token
     within the same window. No route state is read or written.
5. Sort rows by `(tick, sequence, event_class, actor_token, other_token)`.
6. Implement `build_conflict_windows(rows, policy)` returning fixed
   `[start, start + window_ticks)` windows from the minimum to maximum tick.
   Empty windows are omitted.
7. Add tests for every event mapping, sort order, token stability, and absence of
   raw ids.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class ConflictEventRow: ...
def conflict_agent_token(agent_id: EntityId) -> str: ...
def conflict_location_token(entity_id: EntityId) -> str: ...
def conflict_event_rows_from_events(events: Sequence[object], *, policy: OrganizedConflictAnalysisPolicy) -> tuple[ConflictEventRow, ...]: ...
def build_conflict_windows(rows: Sequence[ConflictEventRow], policy: OrganizedConflictAnalysisPolicy) -> tuple[tuple[ConflictEventRow, ...], ...]: ...
```

Compatibility: consumes existing `world.events` values; adds no event. `Died`
links to the prior `Attacked` row by target token and tick, never by actor
identity when the actor is absent.

### Requirement Evidence

- Source: Original Request — "detect sustained organized conflict from event
  patterns".
- Source: `src/world/events.py` 371-472, 580-634, 744-867, 968-983, 1107-1215,
  2728-2752.
- Source: `src/analysis/diplomacy_objective.py` 40-72 — objective anchor pattern;
  do not copy its `AttackApplied`/`HarmApplied` class-name mismatch.
- Supported combinations: attack, flee, death, assistance, capture, structure
  opposition, movement, co-movement, contact, empty stream.

### Error Handling and Logging

- Unknown event detail type -> skipped with WARN count
  `organized_conflict_unknown_event count=%s`.
- Malformed actor/target -> row skipped with WARN count, never invented.
- DEBUG `organized_conflict_objective_rows count=%s windows=%s`.
- Never log raw ids or event payloads.

### Tests

- `tests/unit/test_organized_conflict_events.py`
  - `test_attack_flee_death_and_help_rows`
  - `test_capture_and_structure_opposition_rows`
  - `test_movement_and_co_movement_rows`
  - `test_tokens_are_stable_and_opaque`
  - `test_windows_are_deterministic`
- Command: `uv run pytest tests/unit/test_organized_conflict_events.py -q`

### Acceptance Criteria

- Every existing relevant event maps to a token-only row.
- No raw agent/location id appears in a row.
- Windows are fixed, sorted, and deterministic.
- No new event or persistence read is added.

### Verification

- `uv run pytest tests/unit/test_organized_conflict_events.py -q`
- Expected: all pass.

## Task 12: Harvest owner rows and keep three layers separate

### Intent

Harvest each owner's conflict ledger without leaking owner claims into objective
detection, and define the only three analysis layer types.

### Implementation Steps

1. Create `src/analysis/organized_conflict_rows.py`.
2. Define `OrganizedConflictHarvestRows` with:
   - `objective_events`
   - `objective_windows`
   - `owner_plans`
   - `owner_participations`
   - `owner_interpretations`
   - `owner_outcomes`
   - `owner_contradictions`
   - `owner_terminations`
   - `owner_episodes`
   - `notices`
3. `harvest_organized_conflict_rows(ledgers, events, policy)`:
   - build objective rows/windows from events;
   - tokenize owner ids with `conflict_agent_token`;
   - copy owner plan/participation/interpretation/outcome/contradiction/
     termination/episode rows with opaque refs;
   - sort every family deterministically;
   - record `notices` for missing/incomplete ledgers;
   - never join owner rows into objective rows.
4. Create `src/analysis/organized_conflict_layers.py`:
   - `ConflictObjectiveRow`: tick, event counts, no owner.
   - `ConflictSubjectiveRow`: owner token, plan/participation/interpretation/
     outcome counts, no candidate id.
   - `ConflictAnalyticalRow`: `oc-` candidate id, classification, participant/
     opponent tokens, side count, hostile counts, org/msoc joins.
   - `ConflictLayerView`: all three plus coverage.
   - `assert_conflict_layer_separation(view)` rejects owner fields in objective
     rows, candidate ids in subjective rows, and any forbidden result field.
5. Add `project_conflict_layers(rows, candidates, alignment)`.
6. Add tests mirroring `test_diplomacy_layers.py`.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class OrganizedConflictHarvestRows: ...
def harvest_organized_conflict_rows(ledgers: Sequence[object], events: Sequence[object], *, policy: OrganizedConflictAnalysisPolicy) -> OrganizedConflictHarvestRows: ...

@dataclass(frozen=True, slots=True)
class ConflictObjectiveRow: ...
@dataclass(frozen=True, slots=True)
class ConflictSubjectiveRow: ...
@dataclass(frozen=True, slots=True)
class ConflictAnalyticalRow: ...
@dataclass(frozen=True, slots=True)
class ConflictLayerView: ...
def assert_conflict_layer_separation(view: ConflictLayerView) -> None: ...
```

Compatibility: only objective rows feed detection. Owner rows are joined after
detection for subjective and analytical projection. `analysis` must not import
`agents.cognition`; `harvest_organized_conflict_rows` accepts duck-typed ledger
objects and reads only public attributes (`owner_id`, `plans`, `participations`,
`observations`, `interpretations`, `outcomes`, `contradictions`,
`terminations`, `episodes`, `notices`). This matches the existing
`analysis.diplomacy_rows` pattern and the import-linter contract.

### Requirement Evidence

- Source: `.ai-factory/ARCHITECTURE.md` Key Principle 1 — separate authorities.
- Source: `src/analysis/diplomacy_layers.py` 35-111 — layer/guard pattern.
- Supported combinations: objective-only rows; owner-only rows; both; empty;
  forbidden field leak.

### Error Handling and Logging

- Leakage raises `ValueError("conflict_layer_leakage")` with the field name only.
- WARN `organized_conflict_harvest_missing_ledger count=%s` and
  `organized_conflict_harvest_partial count=%s`.
- DEBUG `organized_conflict_harvest objective=%s owner=%s analytical=%s`.
- Never log tokens or row content.

### Tests

- `tests/unit/test_organized_conflict_layers.py`
  - `test_objective_rows_have_no_owner_or_candidate`
  - `test_subjective_rows_have_no_candidate_id`
  - `test_analytical_rows_reject_forbidden_fields`
  - `test_projection_is_sorted_and_guarded`
- Command: `uv run pytest tests/unit/test_organized_conflict_layers.py -q`

### Acceptance Criteria

- Three distinct layer types exist.
- Objective detection receives no owner claim.
- Leakage fails hard.
- Harvest is deterministic and token-only.

### Verification

- `uv run pytest tests/unit/test_organized_conflict_layers.py -q`
- Expected: all pass.

## Task 13: Detect individual organized and persistent inter-group episodes

### Intent

Define the actual research classification from event patterns. The detector must
be deterministic, explainable by counts, and independent of owner interpretation.

### Implementation Steps

1. Create `src/analysis/organized_conflict_detection.py`.
2. Define `ConflictEpisodeCandidate` with:
   `candidate_key`, `classification`, `start_tick`, `end_tick`,
   `participant_tokens`, `opponent_tokens`, `side_count`,
   `hostile_event_count`, `active_window_count`, `reciprocal_window_count`,
   `role_counts`, `event_classes`, `sustained`, `region_tokens`.
3. Algorithm:
   1. Filter hostile classes: `attack`, `retreat` only when `success is False`
      and a threat exists, `structure_opposition`, `custody_capture` only when
      linked to a hostile component, `death` linked to an attack.
   2. For each window, build an actor graph: connect two actors when they attack
      the same target token or are attacked by the same actor token.
   3. Connected components with at least two actors are candidate sides.
   4. Opponents are the attacked target tokens or attacker tokens not in the
      component.
   5. If a component has fewer than two actors, keep it as a single-actor
      component for `individual_violence`.
   6. Merge adjacent windows into one episode when participant sets overlap by at
      least `min_side_actors` or opponent sets overlap by at least one. Merge is
      transitive and deterministic.
   7. Count hostile events, active windows, reciprocal windows, side actor
      counts, and role evidence. A reciprocal window has at least one hostile
      row from side A to side B and at least one from side B to side A; adjacent
      windows may satisfy reciprocity as a pair.
   8. Derive `route_denial` evidence when a failed `retreat` row with a threat and
      a hostile `attack` row share an endpoint token in the same window. This is
      evidence only; no route is marked blocked.
   9. Classify:
      - `individual_violence` when the episode has one actor token on one side,
        one opponent token, and one active window.
      - `coordinated_conflict` when a side has at least `min_side_actors` and
        hostile events at least `min_hostile_events`. A single-window coordinated
        clash is still coordinated; set a separate `recurrent` flag when active
        windows reach `min_coordinated_windows`.
      - `persistent_inter_group_conflict` when there are at least
        `inter_group_min_sides` sides, each with at least
        `inter_group_min_actors_per_side`, reciprocal windows at least
        `reciprocal_min_windows`, active windows at least `min_windows`, and
        sustained thresholds (`sustained_span_ticks`, `sustained_min_hostile_events`,
        `sustained_min_active_ticks`).
   10. Set `sustained=True` only for episodes meeting the sustained thresholds.
4. Add `classify_conflict_episode(counts, policy)` as a pure function for tests.
5. Add tests for:
   - one attacker/one target -> individual;
   - two attackers/one target repeated -> coordinated;
   - two sides of two actors reciprocal -> persistent inter-group;
   - high damage but one actor -> individual;
   - many actors but one window -> coordinated, not persistent;
   - no hostile events -> empty;
   - deterministic merge order.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class ConflictEpisodeCandidate: ...
def detect_organized_conflict_episodes(rows: Sequence[ConflictEventRow], *, policy: OrganizedConflictAnalysisPolicy) -> tuple[ConflictEpisodeCandidate, ...]: ...
def classify_conflict_episode(counts: Mapping[str, object], *, policy: OrganizedConflictAnalysisPolicy) -> str: ...
```

Compatibility: detection receives objective rows only. It never accepts a
ledger, owner token, interpretation, or relation score.

### Requirement Evidence

- Source: Original Request — distinguish individual violence from persistent
  coordinated inter-group conflict.
- Source: Task 2 locked policy — exact thresholds.
- Source: `src/analysis/diplomacy_detection.py` — deterministic candidate pattern.
- Supported combinations: the seven cases listed above.

### Error Handling and Logging

- Empty rows -> empty tuple, no error.
- Unresolved tokens -> excluded from sides, WARN count
  `organized_conflict_detection_unresolved count=%s`.
- DEBUG `organized_conflict_detection episodes=%s organized=%s
  persistent=%s`.
- Never log participant tokens or target tokens.

### Tests

- `tests/unit/test_organized_conflict_detection.py`
- Command: `uv run pytest tests/unit/test_organized_conflict_detection.py -q`

### Acceptance Criteria

- The three classes are exhaustive for non-empty hostile patterns.
- Individual violence requires one actor and one target with no recurrence.
- Coordinated requires at least two actors on a side and recurrence.
- Persistent inter-group requires two sides, reciprocal windows, and sustained
  thresholds.
- No owner claim influences classification.

### Verification

- `uv run pytest tests/unit/test_organized_conflict_detection.py -q`
- Expected: all pass.

## Task 14: Add episode lineage read-only identity joins and interpretation alignment

### Intent

Give episodes stable analytical identities, forward-only lineage, read-only
organization/macro-society joins, and a researcher-only comparison with owner
interpretations.

### Implementation Steps

1. Create `src/analysis/organized_conflict_identity.py`.
2. `assign_organized_conflict_identities(candidates)`:
   - candidate key = SHA-256 over sorted participant tokens, sorted opponent
     tokens, classification, and start tick;
   - candidate id = `oc-` + 16 hex from key + creation tick;
   - IDs are content-addressed from creation evidence only.
3. `derive_organized_conflict_lineage(candidates)`:
   - edges `oc-edge-` + 16 hex over `(from_id, to_id, kind, tick)`;
   - forward-only kinds: `continued`, `transformed`, `split`, `merge`, `ended`;
   - no backward edge and no reclassification of prior rows.
4. `join_organized_conflict_identities(candidates, organization_candidates,
   macro_society_candidates)`:
   - attach existing `org-`/`msoc-` ids when participant/member tokens overlap;
   - never create, rename, split, merge, or dissolve an identity;
   - unresolved joins stay empty.
5. Create `src/analysis/organized_conflict_alignment.py`.
6. `align_conflict_interpretations(owner_interpretations, candidates)`:
   - match each owner interpretation to a candidate by overlapping participant/
     opponent tokens and a tick inside the candidate window; never by a shared
     numeric id;
   - map candidate classification to an expected interpretation kind;
   - role-specific kinds (`defense`, `retreat`, `assistance`,
     `resource_capture`, `route_blocking`, `structure_attack`) are `consistent`
     when the corresponding event class is present in the candidate, even if the
     overall classification differs;
   - `individual_violence` vs a multi-actor candidate -> `inconsistent`;
   - `coordinated_conflict` vs a persistent candidate -> `consistent` (the
     owner named a subset of the pattern);
   - missing candidate or insufficient evidence -> `unresolved`;
   - no conflict -> `not_applicable`.
7. `summarize_organized_conflict(rows, candidates, alignment)` returns counts and
   coverage only.
8. Add tests for stable IDs, forward-only lineage, read-only joins, and every
   alignment value.

### Required Interfaces and Contracts

```python
def assign_organized_conflict_identities(candidates: Sequence[ConflictEpisodeCandidate]) -> tuple[ConflictEpisodeCandidate, ...]: ...
def derive_organized_conflict_lineage(candidates: Sequence[ConflictEpisodeCandidate]) -> tuple[ConflictLineageEdge, ...]: ...
def join_organized_conflict_identities(candidates, organization_candidates, macro_society_candidates) -> tuple[ConflictEpisodeCandidate, ...]: ...
def align_conflict_interpretations(interpretations, candidates) -> tuple[ConflictAlignmentRow, ...]: ...
def summarize_organized_conflict(...) -> ConflictAnalysisSummary: ...
```

Compatibility: `oc-` and `oc-edge-` must not collide with `dip-`, `org-`,
`msoc-`, `evid-`, `fdisp-`, or `rep-`.

### Requirement Evidence

- Source: `src/analysis/diplomacy_identity.py` 142-349 — identity/lineage/join
  pattern.
- Source: `.ai-factory/ARCHITECTURE.md` "analysis is read-only".
- Supported combinations: consistent, unresolved, inconsistent,
  not_applicable; no candidate; partial role match; org/msoc join and no join.

### Error Handling and Logging

- Duplicate candidate IDs -> `ValueError("conflict_duplicate_candidate")`.
- Backward edge -> `ValueError("conflict_backward_lineage")`.
- DEBUG `organized_conflict_identity candidates=%s edges=%s joins=%s`.
- Never log tokens or joined identity ids.

### Tests

- `tests/unit/test_organized_conflict_identity.py`
- `tests/unit/test_organized_conflict_alignment.py`
- Command:
  `uv run pytest tests/unit/test_organized_conflict_identity.py tests/unit/test_organized_conflict_alignment.py -q`

### Acceptance Criteria

- Candidate IDs are stable and content-addressed.
- Lineage is forward-only.
- `org-`/`msoc-` joins never mint or mutate identity.
- Alignment is researcher-only and never reaches cognition.

### Verification

- Commands above.
- Expected: all pass.

## Task 15: Add four metric families and raise the catalog to 172

### Intent

Append four detached families with exact value keys, no composite score, and one
assembly path used by both completed-run harvest and metric service.

### Implementation Steps

1. In `src/analysis/specifications.py`:
   - change `METRIC_FAMILY_COUNT` to `172`;
   - add `ORGANIZED_CONFLICT_PARTICIPATION`, `ORGANIZED_CONFLICT_PERSISTENCE`,
     `ORGANIZED_CONFLICT_OUTCOMES`, `ORGANIZED_CONFLICT_INTERPRETATION` after
     `TREATY_ANCHOR_COVERAGE`;
   - add four `_spec_*` builders after `_spec_treaty_anchor_coverage` (around
     7814);
   - append them to `_BUILDERS` after the treaty tail (around 7985).
2. Value keys exactly:
   - participation: `episode_count`, `individual_episode_count`,
     `coordinated_episode_count`, `persistent_inter_group_episode_count`,
     `participant_count`, `side_count`, `attacker_count`, `defender_count`,
     `scout_count`, `blocker_count`, `capturer_count`, `assistant_count`,
     `retreater_count`, `messenger_count`, `unknown_role_count`,
     `organized_episode_ratio`, `role_coverage_ratio`.
   - persistence: `active_window_count`, `episode_duration_ticks_total`,
     `episode_duration_ticks_max`, `recurrent_episode_count`,
     `sustained_episode_count`, `inter_group_episode_count`,
     `reciprocal_window_count`, `escalation_count`, `deescalation_count`,
     `hostile_event_count`, `persistence_ratio`.
   - outcomes: `attack_event_count`, `hit_count`, `miss_count`, `damage_total`,
     `lethal_attack_count`, `death_count`, `flee_success_count`,
     `flee_failure_count`, `custody_capture_count`, `structure_opposition_count`,
     `assistance_count`, `co_movement_count`, `route_denial_evidence_count`,
     `outcome_coverage_ratio`.
   - interpretation: `interpretation_count`, `individual_interpretation_count`,
     `coordinated_interpretation_count`,
     `persistent_inter_group_interpretation_count`,
     `defense_interpretation_count`, `retreat_interpretation_count`,
     `assistance_interpretation_count`, `resource_capture_interpretation_count`,
     `route_blocking_interpretation_count`,
     `structure_attack_interpretation_count`, `unclear_interpretation_count`,
     `aligned_count`, `unresolved_count`, `inconsistent_count`,
     `not_applicable_count`, `owner_disagreement_count`,
     `interpretation_coverage_ratio`.
3. Create `src/analysis/organized_conflict_metrics.py` with `_document`,
   `_availability`, `_coverage`, and four compute functions.
   `owner_disagreement_count` is the number of matched episodes with at least two
   owner interpretations of different kinds; it is not a truth or correctness
   measure.
4. In `src/analysis/metric_service.py`:
   - add `MetricComputationInputs` fields `organized_conflict_rows`,
     `organized_conflict_objective_rows`, and
     `organized_conflict_interpretation_alignment`;
   - add one block after diplomacy that harvests, detects, assigns identities,
     joins read-only, projects layers, aligns, summarizes, and wraps all four
     computes in `_safe(...)`.
   - Add a single `organized_conflict_harvest` convenience path only if it
     reduces duplication; the three explicit fields remain the contract.
5. In `src/experiments/collectors.py`, add a completed-run bridge after the
   diplomacy block (around 871-893):
   - read `getattr(arm.runner_result, "organized_conflict_ledgers", None)`;
   - skip when absent;
   - build `entity_to_agent` from `arm.assignment.runner_config.agents`;
   - call `harvest_organized_conflict_rows` on the ledgers and
     `conflict_event_rows_from_events(events or (),
     policy=default_organized_conflict_analysis_policy())`;
   - detect episodes, assign identities, derive lineage, join read-only
     `org-`/`msoc-` candidates when present, project layers, and call
     `align_conflict_interpretations`;
   - `replace(inputs, organized_conflict_rows=..., ...)` with the three fields.
6. Ensure the completed-run path in Task 18 calls the same functions; do not
   duplicate detection logic.
7. Add tests for exact value keys, absent -> empty values, present -> counts,
   assembly emits all four, first 168 order unchanged, and a completed-run
   collector test that all four documents appear when
   `organized_conflict_ledgers` is present.

### Required Interfaces and Contracts

```python
def compute_organized_conflict_participation(...) -> MetricDocument: ...
def compute_organized_conflict_persistence(...) -> MetricDocument: ...
def compute_organized_conflict_outcomes(...) -> MetricDocument: ...
def compute_organized_conflict_interpretation(...) -> MetricDocument: ...
```

Compatibility: `MetricFamilyId` order appends at the end; the first 168 members
keep their order, IDs, versions, and value keys.

### Requirement Evidence

- Source: Original Request — research analytics.
- Source: `src/analysis/specifications.py` 53, 238-245, 7384-7814, 7978-8032.
- Source: `src/analysis/diplomacy_metrics.py` 56-125 — document helper.
- Supported combinations: no conflict rows -> absent/empty; individual-only;
  coordinated-only; persistent inter-group; mixed interpretations.

### Error Handling and Logging

- A compute failure returns an unavailable document through `_safe`; it never
  aborts other families.
- WARN `organized_conflict_metric_unavailable family=%s reason_code=%s`.
- INFO `organized_conflict_metrics_assembled families=4`.
- Never log metric values that contain tokens.

### Tests

- `tests/unit/test_organized_conflict_metrics.py`
- `tests/unit/test_organized_conflict_catalog.py`
- `tests/unit/test_organized_conflict_collectors.py`
- Command:
  `uv run pytest tests/unit/test_organized_conflict_metrics.py tests/unit/test_organized_conflict_catalog.py tests/unit/test_organized_conflict_collectors.py -q`

### Acceptance Criteria

- Catalog is exactly 172.
- The four families are last and their value keys match formulas exactly.
- No composite, war, violence, legitimacy, or winner value exists.
- The first 168 families are unchanged.
- Real assembly emits all four documents.

### Verification

- Commands above.
- Expected: all pass.

## Phase Risks and Mitigations

- Risk: detection uses owner interpretations and becomes circular.
  Mitigation: `detect_organized_conflict_episodes` accepts only
  `ConflictEventRow`; a type/test guard rejects ledgers.
- Risk: objective rows leak raw ids.
  Mitigation: tokenization at row construction and a snapshot/API test for raw
  ids.
- Risk: the detector labels any multi-actor fight as persistent.
  Mitigation: exact three-class tests and locked thresholds.
- Risk: the metric catalog drifts from the enum.
  Mitigation: `validate_metric_catalog` and a first-168 digest.
- Risk: two assembly paths disagree.
  Mitigation: Task 18 reuses the same compute functions and tests exact counts.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
