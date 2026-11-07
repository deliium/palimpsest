# Phase 3: Detached Detection and Metrics

Plan: [index.md](index.md)
Tasks: 11-15
Depends on: Phase 2 / Tasks 4-10

## Objective

Build the detached, read-only border analysis: physical-control rows from
committed events, owner claims and agreements from exported ledgers, a hard
four-layer separation, deterministic overlap/dispute/recognition detection,
analytical control patterns, forward-only identity lineage, researcher-only
alignment, and four appended metric families (catalog 172 -> 176). Analysis never
feeds cognition, prompts, memory, world state, stop selectors, observer
semantics, or Godot.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/analysis/specifications.py` | `METRIC_FAMILY_COUNT = 172` 52-53; last enum 246-249; last specs 7971-8024; builders 8196-8199 | Exact append point and pin |
| `src/analysis/organized_conflict_contract.py` | forbidden fields 35-50; closed enums 53-91 | Newest V4 analysis contract pattern |
| `src/analysis/organized_conflict_rows.py` | `OrganizedConflictHarvestRows` 34-138 | Harvest rows pattern; never cross-joins |
| `src/analysis/organized_conflict_events.py` | event extraction 30-52, 71-101, 143-357 | Committed-event-only extraction |
| `src/analysis/organized_conflict_detection.py` | detection 33-83, 93-119, 259+ | Deterministic window detection |
| `src/analysis/organized_conflict_identity.py` | ids 43-72; lineage 98-148; joins 176-213 | Content-addressed candidate/lineage pattern |
| `src/analysis/organized_conflict_layers.py` | `assert_conflict_layer_separation` 115-133 | Hard leakage guard |
| `src/analysis/organized_conflict_alignment.py` | alignment 48-200 | Researcher-only alignment |
| `src/analysis/organized_conflict_metrics.py` | document helper 45-121; calculations 200-429 | Metric document pattern |
| `src/analysis/spatial_control_metrics.py` | `SpatialActionRow` 83-93; `SpatialClaimRow` 95-103; `compute_spatial_control` 114-186 | Existing physical/claim analysis to reuse, not rewrite |
| `src/experiments/composition.py` | `spatial_action_rows_from_events` 1168-1259; `claim_rows_from_ledgers` 2202-2223 | Existing event-to-row helpers |
| `src/analysis/metric_service.py` | input fields 241-242, 321-327; spatial assembly 621-632; conflict assembly 2034-2132 | Registration point for new rows |
| `src/analysis/diplomacy_contract.py` | layer/alignment enums 73-156 | Layer-separation precedent |
| `docs/analysis-metrics.md` | catalog 7-41; spatial family 31-33; conflict families 604-611 | Documentation and count pins |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/analysis/borders_contract.py` | modify | Add the four-layer row contract and forbidden result fields |
| `src/analysis/borders_rows.py` | create | Harvest owner rows and commit-event physical rows |
| `src/analysis/borders_events.py` | create | Deterministic event extraction and actor/location tokens |
| `src/analysis/borders_layers.py` | create | Four-layer projection and leakage guard |
| `src/analysis/borders_detection.py` | create | Overlap, dispute, recognition, and control-pattern detection |
| `src/analysis/borders_identity.py` | create | `bord-` candidates, lineage, read-only `org-`/`msoc-` joins |
| `src/analysis/borders_alignment.py` | create | Researcher-only alignment and summary |
| `src/analysis/borders_metrics.py` | create | Four metric documents |
| `src/analysis/specifications.py` | modify | Four enum values, specs, builders; count 172 -> 176 |
| `src/analysis/metric_service.py` | modify | Register border row inputs and four families |
| `tests/unit/test_borders_rows.py` | modify | Worker additions only if needed; no duplicate Task 4 coverage |
| `tests/unit/test_borders_events.py` | create | Event extraction tests |
| `tests/unit/test_borders_layers.py` | create | Four-layer separation tests |
| `tests/unit/test_borders_detection.py` | create | Overlap/pattern/recognition tests |
| `tests/unit/test_borders_identity.py` | create | Candidate/lineage/join tests |
| `tests/unit/test_borders_alignment.py` | create | Alignment tests |
| `tests/unit/test_borders_metrics.py` | create | Four metric documents and determinism |
| `tests/unit/test_borders_catalog.py` | create | Catalog 176 and first-172 stability |

## Task 11: Harvest physical-control rows from committed events

### Intent

Derive objective physical-use rows from existing committed events without
inventing an owner, a controller, a title, or a country. Physical control is a
description of repeated presence and use, not ownership.

### Implementation Steps

1. Create `src/analysis/borders_events.py` with:
   - `BORDER_ACTOR_PREFIX = "bactor-"`
   - `BORDER_LOCATION_PREFIX = "bloc-"`
   - `border_agent_token(value: object) -> str` and
     `border_location_token(value: object) -> str` using SHA-256 prefixes; never
     expose raw `AgentId`/`EntityId`.
   - `PhysicalUseEvent` frozen dataclass: `tick`, `location_token`,
     `actor_token`, `kind` (`presence`, `use`, `hostile`, `assistance`,
     `structure`), `action_code`, `source_event_token`.
2. Extract only these committed event classes:
   - presence: `Moved`, `JourneyStarted`, `JourneyArrived`, `JourneyEnded`,
     `ContactRecorded`;
   - use: `Searched`, `Taken`, `TakenFromCorpse`, `ResourceHarvested`,
     `ItemStored`, `Slept`, `StructureBuilt`, `StructureRepaired`,
     `ProjectContributed`, `PublicGoodBenefit`, `ExchangeCompleted`;
   - hostile: `Attacked`, `Fled`, `Died`, `PublicGoodOpposed`;
   - assistance: `Helped`, `Fed`, `Transported`.
   Use only the event fields present on the committed event; never read a live
   world state, an agent body, or a ledger.
3. Resolve the location for each event:
   - `Moved` -> destination;
   - `JourneyStarted` -> origin;
   - `JourneyArrived`/`JourneyEnded` -> destination;
   - `ContactRecorded` -> contact location;
   - all others -> the event's location field.
   If an event has no location, emit no row (do not guess).
4. Group events into fixed windows of `policy.physical_window_ticks = 6` ticks,
   anchored at tick 0. Sort events by `(tick, action_code, actor_token,
   source_event_token)` before grouping.
5. For each `(location_token, window_start)` emit `BorderPhysicalRow`:
   - `location_token`
   - `window_start`, `window_end`
   - `actor_count` (distinct actor tokens)
   - `action_count` (all use/presence/hostile/assistance rows)
   - `hostile_count`
   - `assistance_count`
   - `presence_ticks` (distinct ticks with a presence row)
   - `classification`: one of `unoccupied` (no rows), `transient` (presence but
     `action_count < min_use_actions`), `repeated_use` (`action_count >=
     min_use_actions`), `shared_use` (`actor_count >= min_distinct_actors`),
     `contested_use` (`hostile_count > 0`). Precedence:
     `contested_use` > `shared_use` > `repeated_use` > `transient` >
     `unoccupied`.
6. Never emit a location with no rows; absence is not `unoccupied` evidence for
   every location. The summary records coverage as `observed`/`partial`/
   `not_applicable`.
7. Add `physical_rows_summary(rows)` with counts only.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class BorderPhysicalRow:
    location_token: str
    window_start: int
    window_end: int
    actor_count: int
    action_count: int
    hostile_count: int
    assistance_count: int
    presence_ticks: int
    classification: str

def harvest_physical_rows(
    committed_events: Sequence[object],
    *,
    policy: BordersAnalysisPolicy,
) -> tuple[BorderPhysicalRow, ...]: ...
```

- No raw actor or location id appears in a row.
- No row has `owner`, `controller`, `sovereign`, or `title`.
- The rows are deterministic for the same event order and policy.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — "WorldEngine knows only locations and occupancy",
  "physical control".
- Source: `src/world/events.py` event classes 372-1215 and 2627-2752.
- Source: `src/analysis/spatial_control_metrics.py` 83-186 for existing
  physical/claim separation.
- Supported combinations: no events; presence only; repeated use; shared use;
  hostile use; assistance only; missing location; each tested.

### Error Handling and Logging

- Unknown event types are skipped at DEBUG; they never fail the run.
- A missing location is skipped and counted in `coverage` as `partial`.
- Logs: `DEBUG borders_physical_rows rows=%s windows=%s coverage=%s`.
- Never log actor, location, or event tokens.

### Tests

- `tests/unit/test_borders_events.py`
  - `test_event_class_to_action_code_is_closed`
  - `test_location_resolution_per_event_kind`
  - `test_fixed_six_tick_windows_and_sort_order`
  - `test_classification_precedence`
  - `test_missing_location_is_partial_not_guessed`
  - `test_no_raw_ids_in_rows`
  - `test_harvest_is_deterministic`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_events.py -q`
- Expected: all pass.

### Acceptance Criteria

- Rows come only from committed events.
- No ownership/control field exists.
- Event windows and classifications are deterministic.
- Missing data is explicit, not invented.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_events.py -q`
- Expected: pass.

## Task 12: Harvest owner border rows and keep four layers separate

### Intent

Turn exported owner ledgers into detached claim, recognition, access, agreement,
and dispute rows, then project exactly four layers: physical control, subjective
claim, agreement, and analytical control pattern. A hard guard fails the build if
one layer leaks into another.

### Implementation Steps

1. Create `src/analysis/borders_rows.py`:
   - `BorderHarvestRows` frozen dataclass with:
     `physical: tuple[BorderPhysicalRow, ...]`,
     `claims: tuple[BorderClaimRow, ...]`,
     `recognitions: tuple[BorderRecognitionRow, ...]`,
     `access_expectations: tuple[BorderAccessRow, ...]`,
     `agreements: tuple[BorderAgreementRow, ...]`,
     `disputes: tuple[BorderDisputeRow, ...]`,
     `notices: tuple[str, ...]`,
     `coverage: str`.
   - `harvest_border_rows(ledgers, committed_events, policy)`:
     - call `harvest_physical_rows`;
     - for each `BorderLedger`, project each row with owner token
       (`border_owner_token`) and opaque domain/location/anchor tokens;
     - never cross-join two owners' rows;
     - never resolve a location against the live world.
2. Define the row contracts in `src/analysis/borders_contract.py`:
   - `BorderClaimRow`: `owner_token`, `domain_token`, `location_tokens`,
     `boundary_edge_tokens`, `status`, `strength`, `anchor_token`.
   - `BorderRecognitionRow`: `recognition_token`, `domain_token`,
     `edge_tokens`, `basis`, `status`.
   - `BorderAccessRow`: `access_token`, `domain_token`, `subject_token`, `mode`,
     `status`.
   - `BorderAgreementRow`: `agreement_token`, `domain_token`,
     `counterparty_token`, `provision_tokens`, `status`, `recognition`,
     `effective_tick`, `expiry_tick`.
   - `BorderDisputeRow`: `dispute_token`, `domain_token`, `counterparty_token`,
     `contested_location_tokens`, `status`.
3. Create `src/analysis/borders_layers.py`:
   - `BorderLayerView` with the four semantic layers:
     - physical: `physical`;
     - subjective claim: `claims`, `recognitions`, `access_expectations`,
       `disputes`;
     - agreement: `agreements`;
     - analytical: `patterns`.
   - `project_border_layers(rows, patterns)` sorts each tuple by its primary key.
   - `assert_border_layer_separation(view)`:
     - physical rows must not contain `owner_token`, `domain_token`,
       `counterparty_token`, `agreement_token`, or `pattern`;
     - claim rows must not contain `actor_count`, `action_count`,
       `hostile_count`, or `classification`;
     - agreement rows must not contain physical counts or analytical pattern;
     - pattern rows may contain derived counts but not raw ids, owner ids, or
       evidence bodies;
     - all rows reject `sovereign`, `legitimate`, `winner`, `loser`, `score`,
       `composite`, `enforced`, `ownership`, `country_owner`.
4. `assert_border_layer_separation` raises
   `ValueError("border_layer_leak:<layer>:<field>")` and logs
   `ERROR borders_layer_leak layer=%s field=%s`.
5. Add `border_rows_summary(rows)` with counts only and a `coverage` value of
   `complete`, `partial`, or `not_applicable`.
6. Do not import `agents.cognition`, `experiments`, `api`, `persistence`, or
   `observer` from the analysis modules. Only detached row types and committed
   events are inputs.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class BorderLayerView:
    physical: tuple[BorderPhysicalRow, ...]
    claims: tuple[BorderClaimRow, ...]
    recognitions: tuple[BorderRecognitionRow, ...]
    access_expectations: tuple[BorderAccessRow, ...]
    disputes: tuple[BorderDisputeRow, ...]
    agreements: tuple[BorderAgreementRow, ...]
    patterns: tuple[BorderPatternRow, ...]

def harvest_border_rows(
    ledgers: Sequence[object],
    committed_events: Sequence[object],
    *,
    policy: BordersAnalysisPolicy,
) -> BorderHarvestRows: ...

def assert_border_layer_separation(view: BorderLayerView) -> None: ...
```

- Four layers are separate Python types.
- A layer leak is a hard failure, not a warning.
- Owner tokens are stable hashes; no raw owner ids.
- The view contains no truth, winner, sovereignty, or enforcement field.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — four overlays must distinguish physical control,
  subjective claim, agreement, analytical control pattern.
- Source: `.ai-factory/ARCHITECTURE.md` — Key Principle 1 and "analysis is
  read-only".
- Source: `src/analysis/organized_conflict_layers.py` 115-133.
- Supported combinations: all four layers present; one layer empty; two owners
  overlap; an agreement without a claim; a physical row without a claim; each
  tested.

### Error Handling and Logging

- A foreign ledger item type is rejected with `TypeError`.
- A layer leak raises and is never downgraded.
- Logs: `DEBUG borders_harvest claims=%s agreements=%s disputes=%s physical=%s`.
- Never log row tokens or owner tokens.

### Tests

- `tests/unit/test_borders_layers.py`
  - `test_four_layer_types_are_distinct`
  - `test_physical_rows_reject_claim_fields`
  - `test_claim_rows_reject_physical_counts`
  - `test_agreement_rows_reject_pattern_fields`
  - `test_pattern_rows_reject_raw_ids_and_forbidden_results`
  - `test_rows_are_sorted_and_deterministic`
  - `test_empty_layers_are_legal`
  - `test_analysis_modules_do_not_import_cognition_or_adapters`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_layers.py -q`
- Expected: all pass.

### Acceptance Criteria

- Four separate types exist and are projected into four layers.
- Leakage is a hard failure.
- No raw ids or forbidden result fields are present.
- Analysis remains import-closed against cognition/adapters.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_layers.py -q`
- `uv run --frozen --python 3.12.14 lint-imports` (if contracts change)
- Expected: pass.

## Task 13: Detect overlaps, disputes, recognized boundaries, and analytical control patterns

### Intent

Compute closed, deterministic classifications from the four layers. Overlap is
set intersection, not a moral claim. A recognized boundary is an owner-belief
alignment, not a truth. A control pattern is a descriptive label, not a winner or
a score.

### Implementation Steps

1. Create `src/analysis/borders_detection.py` with:
   - `BorderOverlapRow`: `left_domain_token`, `right_domain_token`,
     `overlap_location_tokens`, `overlap_count`, `dispute_status`.
   - `BorderPatternRow`: `pattern_token`, `domain_token`,
     `location_tokens`, `pattern`, `physical_actions`, `claim_count`,
     `agreement_count`, `dispute_count`.
   - `detect_border_overlaps(claims, policy)`:
     - sort claims by `(domain_token, owner_token)`;
     - compare every pair of **different owners** only;
     - exact set intersection of location tokens;
     - emit one row per `(left, right)` with sorted tokens;
     - no pair is merged or ranked.
   - `detect_border_disputes(overlaps, agreements, policy)`:
     - an overlap without an agreement covering both parties is a
       `disputed` row;
     - an overlap with an agreement whose provisions include
       `territorial_acknowledgement` is `acknowledged` but still retained as an
       overlap;
     - no winner, no resolution, no forced boundary.
   - `detect_boundary_recognitions(recognitions, disputes)`:
     - recognized if at least one recognition row has `status=recognized` and no
       dispute for the same edge;
     - unresolved if no recognition and no dispute;
     - disputed if any dispute references the edge.
   - `detect_control_patterns(physical, claims, agreements, disputes, policy)`:
     - for each domain, count physical rows whose location tokens intersect the
       domain;
     - pattern precedence:
       `contested` if any dispute or any hostile physical row;
       `agreement_contested` if an agreement exists and a dispute exists;
       `agreement_aligned` if an agreement exists and physical actions >=
       `control_pattern_min_physical_actions`;
       `claim_overlap` if the domain overlaps another owner's claim;
       `claim_aligned` if a claim exists and physical actions >=
       `control_pattern_min_physical_actions`;
       `claim_only` if a claim exists and no physical actions;
       `physical_unclaimed` if physical actions exist and no claim;
       `unclaimed` otherwise;
       `unknown` when the evidence is incomplete.
   - Emit `BorderControlSummary` with pattern distribution and denominators.
2. No composite score. Counts and ratios are quantized to 1e-6 with a
   `denominator_kind` and explicit zero/empty policy.
3. The detector never reads owner ledgers, the world engine, an observer frame,
   or another analysis family's private state.
4. Add `border_detection_notices(...)` for `insufficient_physical_evidence`,
   `overlap_only`, `agreement_without_claim`, `claim_without_observation`.
5. Sort all rows by `(pattern_token, domain_token, left, right)`.

### Required Interfaces and Contracts

```python
def detect_border_overlaps(
    claims: Sequence[BorderClaimRow], *, policy: BordersAnalysisPolicy
) -> tuple[BorderOverlapRow, ...]: ...

def detect_control_patterns(
    physical: Sequence[BorderPhysicalRow],
    claims: Sequence[BorderClaimRow],
    agreements: Sequence[BorderAgreementRow],
    disputes: Sequence[BorderDisputeRow],
    *,
    policy: BordersAnalysisPolicy,
) -> tuple[BorderPatternRow, ...]: ...
```

- Overlap requires different owners.
- A shared location is retained by both claims; it is never assigned to one
  owner.
- Pattern labels are closed.
- No `winner`, `loser`, `sovereignty`, `legitimacy`, `score`, or `composite`
  field exists.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — overlapping claims, disputed borders, recognized
  boundaries, analytical control pattern.
- Source: `src/analysis/spatial_control_metrics.py` 385-395 for claim-contest
  logic; the new detector does not modify it.
- Source: `.ai-factory/ARCHITECTURE.md` — analysis is read-only and never
  reconciles owner beliefs.
- Supported combinations: no claims; one claim; two overlapping claims; two
  disjoint claims; agreement over overlap; dispute over overlap; physical use
  without a claim; hostile use; each tested.

### Error Handling and Logging

- Invalid/oversize inputs raise `ValueError("borders_detection: <code>")`.
- Incomplete evidence yields an `unknown`/`unresolved` label, never a guess.
- Logs: `DEBUG borders_detection overlaps=%s disputes=%s patterns=%s`.
- Never log tokens or location sets.

### Tests

- `tests/unit/test_borders_detection.py`
  - `test_overlap_requires_different_owners`
  - `test_overlap_retains_all_shared_locations`
  - `test_dispute_is_retained_without_winner`
  - `test_agreement_overlap_is_acknowledged_but_not_reconciled`
  - `test_recognition_precedence`
  - `test_control_pattern_precedence_and_unknown`
  - `test_no_composite_or_winner_field`
  - `test_detection_is_deterministic_and_sorted`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_detection.py -q`
- Expected: all pass.

### Acceptance Criteria

- Overlap and dispute detection is deterministic and retains both claims.
- Control patterns are closed labels with explicit denominators.
- No winner, sovereignty, legitimacy, or composite score exists.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_detection.py -q`
- Expected: pass.

## Task 14: Add domain lineage, read-only identity joins, and researcher-only alignment

### Intent

Give detached border analysis stable candidate identities and forward-only
lineage, join existing `org-`/`msoc-` identities without mutating them, and
classify interpretation alignment for researchers only. Alignment never reaches
cognition, prompts, memory, world state, stop selectors, observer semantics, or
Godot.

### Implementation Steps

1. Create `src/analysis/borders_identity.py`:
   - `BORDER_CANDIDATE_PREFIX = "bord-"`
   - `BORDER_EDGE_PREFIX = "bord-edge-"`
   - `BorderCandidate`: `candidate_id`, `location_tokens`,
     `boundary_edge_tokens`, `status`, `evidence_count`, `first_tick`,
     `last_tick`.
   - `assign_border_identities(claims, patterns)`:
     - candidate id = SHA-256 of sorted location tokens plus the first
       creation evidence token;
     - same content -> same id;
     - no owner token in the id.
   - `derive_border_lineage(candidates)`:
     - compare consecutive candidate snapshots by location-set containment;
     - labels: `emerged`, `continued`, `transformed`, `split`, `merge`,
       `dissolved`;
     - forward-only parent/child edges; never rewrite an earlier edge.
   - `join_border_identities(candidates, org_candidates, macro_candidates)`:
     - read-only anchor matches only;
     - never mint, rename, split, merge, or dissolve `org-`/`msoc-` ids.
2. Create `src/analysis/borders_alignment.py`:
   - `BorderAlignmentRow`: `candidate_id`, `alignment`, `claim_alignment`,
     `agreement_alignment`, `pattern_alignment`, `basis_counts`.
   - `align_border_interpretations(claims, agreements, patterns)`:
     - `consistent` only when a claim, an agreement, and a physical/pattern row
       agree on the same location set and no dispute exists;
     - `inconsistent` only when two retained owner rows conflict on the same
       location (overlap without acknowledgement, agreement vs dispute);
     - `unresolved` when a required layer is missing;
     - `not_applicable` when there is no candidate.
   - `summarize_borders(...)`: counts, coverage, alignment distribution,
     notices. No truth/winner/legitimacy.
3. Add `BorderAnalysisSummary` with:
   - `candidate_count`, `claim_count`, `agreement_count`, `dispute_count`,
     `physical_row_count`, `pattern_count`
   - `alignment_counts: tuple[tuple[str, int], ...]`
   - `coverage: str`
   - `policy_version`, `catalog_version`.
4. No alignment value is imported by `agents.cognition`, `simulation`,
   `observer`, `api`, or `persistence`.

### Required Interfaces and Contracts

```python
def assign_border_identities(
    claims: Sequence[BorderClaimRow], patterns: Sequence[BorderPatternRow]
) -> tuple[BorderCandidate, ...]: ...

def derive_border_lineage(
    candidates: Sequence[BorderCandidate],
) -> tuple[BorderLineageEdge, ...]: ...

def align_border_interpretations(
    claims: Sequence[BorderClaimRow],
    agreements: Sequence[BorderAgreementRow],
    patterns: Sequence[BorderPatternRow],
) -> tuple[BorderAlignmentRow, ...]: ...
```

- Candidate ids are content-addressed and owner-independent.
- Lineage is forward-only.
- `org-`/`msoc-` joins are read-only.
- Alignment is researcher-only.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — "Agents and societies may interpret the same events
  differently" (applies to claims/borders) and the four-layer distinction.
- Source: `.ai-factory/ARCHITECTURE.md` — analysis is read-only; identities are
  not minted from analysis.
- Source: `src/analysis/organized_conflict_identity.py` 43-213.
- Supported combinations: emerged/continued/transformed/split/merge/dissolved;
  org join hit/miss; macro join hit/miss; consistent/unresolved/inconsistent/
  not_applicable; each tested.

### Error Handling and Logging

- A join target of the wrong type is ignored with `join_unresolved`, never
  mutated.
- Invalid lineage raises `ValueError("borders_lineage: <code>")`.
- Logs: `DEBUG borders_identity candidates=%s lineage_edges=%s joined_org=%s`.
- Never log candidate ids, owner tokens, or org/msoc ids.

### Tests

- `tests/unit/test_borders_identity.py`
  - `test_candidate_id_is_content_addressed_and_owner_independent`
  - `test_lineage_is_forward_only_and_covers_all_six_labels`
  - `test_org_and_msoc_joins_are_read_only`
  - `test_alignment_matrix`
  - `test_missing_layer_is_unresolved_not_inconsistent`
  - `test_summary_has_counts_and_no_truth_field`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_identity.py -q`
- Expected: all pass.

### Acceptance Criteria

- Candidate identities and lineage are deterministic.
- `org-`/`msoc-` identities are never mutated.
- Alignment is closed and researcher-only.
- No truth/winner/legitimacy field exists.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_identity.py -q`
- Expected: pass.

## Task 15: Add four metric families and raise the catalog to 176

### Intent

Append exactly four scalar metric families without changing the first 172. The
families describe claim structure, overlap/contest, agreement/recognition, and
control alignment. No composite border score exists.

### Implementation Steps

1. In `src/analysis/specifications.py`:
   - Add enum values after `ORGANIZED_CONFLICT_INTERPRETATION` (line 249):
     - `BORDER_CLAIM_STRUCTURE = "border_claim_structure"`
     - `BORDER_OVERLAP_CONTEST = "border_overlap_contest"`
     - `BORDER_AGREEMENT_RECOGNITION = "border_agreement_recognition"`
     - `BORDER_CONTROL_ALIGNMENT = "border_control_alignment"`
   - Change `METRIC_FAMILY_COUNT` from 172 to 176 at line 53.
   - Add `_spec_border_claim_structure` after the last V4-12 spec (8024):
     - population: `detached_border_claim_rows`
     - denominator: `candidate_domains`
     - formulas: `domain_count`, `location_count`, `boundary_edge_count`,
       `claim_status_distribution`, `anchor_resolution_ratio`
     - value keys: `domain_count`, `location_count`, `boundary_edge_count`,
       `claimed_count`, `recognized_count`, `disputed_count`,
       `anchor_resolved_ratio`.
   - Add `_spec_border_overlap_contest`:
     - population: `detached_border_overlap_rows`
     - denominator: `claim_pairs`
     - formulas: `overlap_pair_count`, `overlap_location_count`,
       `dispute_count`, `reciprocal_claim_count`, `dispute_status_distribution`.
   - Add `_spec_border_agreement_recognition`:
     - population: `detached_border_agreement_rows`
     - denominator: `agreement_domains`
     - formulas: `agreement_count`, `agreement_status_distribution`,
       `recognition_count`, `access_mode_distribution`,
       `provision_distribution`, `recognized_edge_ratio`.
   - Add `_spec_border_control_alignment`:
     - population: `detached_border_pattern_rows`
     - denominator: `observed_domains`
     - formulas: `pattern_distribution`, `physical_use_ratio`,
       `claim_alignment_ratio`, `agreement_alignment_ratio`,
       `alignment_distribution`, `coverage_ratio`.
   - Append the four builders to `_BUILDERS` after the organized-conflict
     builders (8196-8199).
   - Use the shared `_base(...)` helper with:
     `cohort_window="6_ticks"`, `deceased_policy="retain_committed_rows"`,
     `zero_holding_policy="emit_zero"`,
     `opportunity_vs_occurrence="occurrence"`,
     `censoring_policy="right_censored"`, `quantization="1e-6"`,
     `evidence_inputs=frozenset({EvidenceStage.AGENT_VISIBLE_PROJECTION})`,
     `empty_case="emit_zero"`, `one_case="emit_value"`,
     `all_zero_case="emit_zero"`, `unknown_case="unavailable_unknown"`,
     `availability_behavior="explicit_not_applicable"`. Detached border rows are
     derived from committed events and exported owner ledgers, the same closed
     evidence stage used by the V4-12 organized-conflict families.
   - Keep every existing family id, order, version, and value key unchanged.
2. In `src/analysis/metric_service.py`:
   - Add input fields `border_claim_rows`, `border_agreement_rows`,
     `border_physical_rows`, `border_pattern_rows`,
     `border_alignment_rows`, `border_overlap_rows`.
   - Add an assembly block that registers the four families through `_safe(...)`
     and follows the existing conflict/diplomacy assembly.
   - Absent rows yield the documented `empty_case`/`unavailable` behavior; never
     infer a metric from another family.
3. Add `tests/unit/test_borders_metrics.py`:
   - each family emits exactly its documented value keys;
   - quantized ratios, integer counts, empty/zero/one/all-zero cases;
   - no composite, winner, sovereignty, or legitimacy key;
   - deterministic output for the same rows.
4. Add `tests/unit/test_borders_catalog.py`:
   - `METRIC_FAMILY_COUNT == 176`;
   - the first 172 family ids and order are unchanged;
   - each new family has a spec, builder, and documented value keys;
   - no duplicate family id;
   - no test file asserts a stale 172 current pin after the sweep.
5. Sweep every **current** `172` pin in `tests/` and current-pin docs to 176;
   leave historical revision statements (for example "164 -> 168" or
   "168 -> 172") unchanged. Use `rg -n "172" tests docs src/analysis/specifications.py`
   and classify each match as current pin or historical statement.

### Required Interfaces and Contracts

```python
class MetricFamilyId(StrEnum):
    ...
    BORDER_CLAIM_STRUCTURE = "border_claim_structure"
    BORDER_OVERLAP_CONTEST = "border_overlap_contest"
    BORDER_AGREEMENT_RECOGNITION = "border_agreement_recognition"
    BORDER_CONTROL_ALIGNMENT = "border_control_alignment"

METRIC_FAMILY_COUNT: Final[int] = 176
```

- Four families, four documents, scalar values only.
- The first 172 families keep id, order, version, and value keys.
- No composite/overall border score.
- The metrics are detached and never feed cognition.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — analytical control pattern and the four-layer
  distinction.
- Source: `src/analysis/specifications.py` 52-53, 246-249, 7971-8024,
  8196-8199.
- Source: `docs/analysis-metrics.md` 7-41 and 604-611.
- Supported combinations: empty rows, one row, all-zero, missing layer, partial
  coverage; each family tested.

### Error Handling and Logging

- A spec/build mismatch raises at import time, not at runtime.
- A missing input row set yields the documented empty/unavailable value.
- Logs: `INFO borders_metrics_registered families=4 catalog=176`.
- Never log row tokens, owner tokens, or metric values at INFO.
- No silent fallback to another analysis family.

### Tests

- `tests/unit/test_borders_metrics.py`
- `tests/unit/test_borders_catalog.py`
- Commands:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_metrics.py tests/unit/test_borders_catalog.py tests/unit/test_metric_specifications.py -q`
- Expected: all pass.

### Acceptance Criteria

- Catalog is exactly 176 with four appended families.
- The first 172 are unchanged.
- Every family has empty/zero/one/all-zero/unknown behavior and value keys.
- No composite border score exists.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_metrics.py tests/unit/test_borders_catalog.py -q`
- `uv run --frozen --python 3.12.14 pytest tests/unit/test_metric_specifications.py tests/unit/test_metric_service.py -q`
- Expected: pass.

## Phase Risks and Mitigations

- Risk: physical control becomes a hidden ownership field.
  Mitigation: Task 11 emits counts and closed classifications only; no owner
  field exists.
- Risk: four layers collapse into one row type.
  Mitigation: Task 12 defines four distinct types and a hard leakage guard.
- Risk: overlap detection implies a winner or a forced boundary.
  Mitigation: Task 13 retains both claims and emits no winner/score.
- Risk: alignment is read as truth.
  Mitigation: Task 14 names it researcher-only; no cognition import exists.
- Risk: metric append changes the first 172.
  Mitigation: Task 15 asserts exact order and add-only behavior.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
