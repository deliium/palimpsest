# Phase 1: Migration-Displacement Contract and Seam

Plan: [index.md](index.md)
Tasks: 1-3
Depends on: none

## Objective

Freeze the closed migration-displacement vocabulary, the origin-route-destination
contract, the locked cognition and analysis policies, and the activation rule
that makes migration beliefs available only when the owned `organizations` V4
context and deterministic regional migration are both active. This phase adds no
runner schema, flag, context, command, event, write pair, API version, or
migration.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/world/regions.py` | `RegionDefinition` 39-48; `LocationRegion` 51-61; `RouteSpec` 64-99; `RegionsMigrationSpec` 102-224; `Journey` 227-297 | Regions are logical labels over locations; routes are adjacent-edge overrides with duration and fatigue; journeys carry origin/destination but no motive |
| `src/world/_travel.py` | `advance_due_journeys` 18-126; `_journey_contact` 129-168; `cancel_dead_journeys` 171-204 | Objective arrival, capacity wait, timeout, and death processing remain unchanged |
| `src/world/_rules.py` | `_evaluate_move` 1167-1196; `_evaluate_transport` 1527-1569; `_evaluate_flee` 1621-1673 | Physical movement is adjacent-only and remains the only movement path |
| `src/world/events.py` | `JourneyStarted` 392-409; `JourneyArrived` 411-440; `JourneyEnded` 442-474; `ContactRecorded` 476-550 | Objective migration evidence is derived from existing events; no event is added |
| `src/agents/cognition/regional_migration.py` | `REGIONAL_DESTINATION_MEMORY_POLICY_VERSION` 28; `REGIONAL_MIGRATION_COGNITION_POLICY_VERSION` 29; `known_destination_ids` 201-272; `destination_action_biases` 275-466 | Existing owner-scoped destination evidence and bounded bias; V4-14 extends it with causes and multi-hop plans |
| `src/agents/cognition/configuration.py` | `CognitionTerritorialClaimMode` 327-331; `CognitionBordersMode` 338-346; `CognitionLoopConfig` 604-760; `build_cognitive_loop` 1724-1965 | Internal cognition configuration seam; no runner key is added |
| `src/simulation/runner.py` | `_cognition_config_for` 1024-1050; regional mode wiring 1187-1215; call sites 2818-2866, 6567-6617, 6947-6991 | Existing derivation point for an internal migration mode; three call sites must agree |
| `src/simulation/v4_architecture.py` | `V4ContextId` 60-76; `ORGANIZATIONS` 110-127 | 14 contexts / 12 flags are closed; no new context or flag |
| `src/simulation/runner_models.py` | `V3CapabilityFlags.multi_polity_migration` 1091; `V4CapabilityFlags` 1130-1145; `regions_migration` 7716; v44/v56 gates 9379-9425, 9653-9685 | The existing V3 flag and v56 V4 seam are the only activation inputs |
| `src/simulation/runner_serialization.py` | v44 root keys 4674-4689; `_REGIONS_MIGRATION_KEYS` 4877-4886; v56 family 4825-4842; encode/decode 6650-6744 | Exact nested keyset must remain unchanged |
| `src/analysis/specifications.py` | `METRIC_FAMILY_COUNT` 52-53; `regional_population@1` 4067-4131; `regional_migration@1` 4134-4184; `regional_destination_beliefs@1` 4187-4219; border `_BUILDERS` tail 8354-8357 | Existing migration metrics must remain byte-identical; V4-14 appends four |
| `tests/architecture/test_v4_architecture_invariants.py` | registry and pin assertions | Must remain green; no context count change |
| `tests/unit/test_runner_config_v44.py` | migration-only round-trip 78; exact nested keys 134 | Existing v44 accepted keyset must stay unchanged |
| `tests/unit/test_regional_migration_cognition.py` | loop builder 240; route+food bias 249; hop bound 311 | Existing deterministic migration behavior must stay byte-compatible when the new mode is disabled |
| `src/agents/cognition/borders.py` | module docstring and closed vocabulary 1-135 | Precedent for an owner-scoped, non-command belief ledger |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/agents/cognition/migration_displacement.py` | create | Closed migration-displacement vocabulary, route contract, locked policy, IDs, ledger rows |
| `src/analysis/migration_displacement_contract.py` | create | Closed detached-analysis vocabulary, forbidden result fields, layer and alignment enums |
| `src/analysis/migration_displacement_policy.py` | create | Locked analysis thresholds and bounded row budgets |
| `src/agents/cognition/configuration.py` | modify | Add internal `CognitionMigrationDisplacementMode`; add mode/policy to `CognitionLoopConfig`; canonical payload keys |
| `src/simulation/runner.py` | modify | Derive migration-displacement mode from `organizations_enabled` and deterministic regional migration at all three `_cognition_config_for` call sites |
| `src/agents/cognition/loop.py` | modify | Accept and store the internal mode/policy; no update call yet |
| `src/agents/cognition/__init__.py` | modify | Export the new public migration-displacement symbols |
| `src/simulation/cognition_contracts.py` | modify | Re-export the internal mode for the simulation layer |
| `tests/unit/test_migration_displacement_contract.py` | create | Vocabulary, ID, route, and forbidden-name tests |
| `tests/unit/test_migration_displacement_policy.py` | create | Locked policy and unsupported-policy tests |
| `tests/unit/test_migration_displacement_activation.py` | create | Activation combinations, v57 absence, no runner key |

## Task 1: Freeze the migration-displacement vocabulary, identifier grammar, and origin-route-destination contract

### Intent

Define the closed nouns that every later phase uses. A migration intent is one
owner's belief about a possible movement from a logical origin through an ordered
logical route to a logical destination. It is not a world object, a refugee
category, a legal status, or a command. A route is an ordered sequence of 2-4
`EntityId` locations whose consecutive pairs are adjacent; no grid, coordinate,
polygon, area, or region conversion exists.

### Implementation Steps

1. Create `src/agents/cognition/migration_displacement.py` with a module
   docstring that states:
   - one owner's belief only;
   - `WorldEngine`, perception, admission, stop selectors, memory, prompts,
     observer semantics, and Godot never read it;
   - no objective cause, wave, refugee, asylum, displacement, integration,
     household, or registry exists;
   - no helper returns, constructs, submits, resolves, or blocks a command.
2. Add the constants:
   - `MIGRATION_DISPLACEMENT_POLICY_VERSION: Final[str] = "migration-displacement.v1"`
   - `MIGRATION_DISPLACEMENT_LEDGER_VERSION: Final[str] = "migration-displacement-ledger.v1"`
   - `MIGRATION_DISPLACEMENT_FRAME_VERSION: Final[str] = "mdp_v1"`
   - `MIGRATION_DISPLACEMENT_FRAME_MAX_CHARS: Final[int] = 256`
   - `MIGRATION_DISPLACEMENT_FRAME_MAX_RELATIONS: Final[int] = 4`
   - `MIGRATION_DISPLACEMENT_FRAME_FIELD_COUNT: Final[int] = 14`
3. Add closed enums:
   - `MigrationCauseKind`: `resource_scarcity`, `environmental_hazard`,
     `conflict`, `opportunity`, `social_network`, `institution`, `unknown`.
   - `MigrationCauseSource`: `direct_observation`, `own_need`, `own_journey`,
     `own_relationship`, `own_kinship`, `organization_belief`,
     `institution_belief`, `formal_rule_belief`, `dispute_belief`,
     `evidence_belief`, `diplomacy_belief`, `conflict_belief`, `border_belief`,
     `testimony`, `inference`, `unknown`.
   - `MigrationIntentStatus`: `considered`, `planned`, `departed`, `arrived`,
     `abandoned`, `expired`, `unknown`.
   - `RouteBeliefBasis`: `direct_observation`, `own_journey`, `testimony`,
     `inference`, `unresolved`.
   - `RouteBeliefStatus`: `open`, `blocked_belief`, `unresolved`, `expired`,
     `unknown`.
   - `ClusterBasis`: `kinship`, `organization`, `co_movement`, `communication`,
     `relationship`, `unknown`.
   - `ClusterStatus`: `believed`, `disputed`, `dissolved`, `expired`, `unknown`.
   - `IntegrationDomain`: `residence`, `needs`, `resource_access`,
     `organization_participation`, `institution_participation`,
     `relationships`, `conflict_status`, `unknown`.
   - `IntegrationStatus`: `settled`, `transient`, `returned`, `onward`,
     `unknown`.
   - `WaveObservationStatus`: `observed`, `reported`, `disputed`, `expired`,
     `unknown`.
   - `CauseEvidenceStatus`: `active`, `superseded`, `contradicted`, `expired`,
     `unknown`.
   - `MigrationNoticeCode`: `unresolved_anchor`, `route_unobserved`,
     `cause_unresolved`, `cluster_unresolved`, `integration_unobserved`,
     `same_root_suppressed`, `intent_cap_reached`, `route_cap_reached`,
     `cause_cap_reached`, `cluster_cap_reached`, `integration_cap_reached`,
     `wave_cap_reached`, `ledger_cap_reached`, `truncated`, `malformed_frame`,
     `peer_claim_untrusted`.
4. Define the pure value helpers:
   - `require_route_locations(value: object, *, field_name: str) -> tuple[EntityId, ...]`
     accepts only an ordered sequence of exact `EntityId`, rejects
     strings/bytes/sets/mappings, rejects duplicates, rejects adjacent repeats
     (same location twice in a row), requires `2 <= len <= 4`, and never sorts
     the route. At this contract layer, "adjacent" means consecutive sequence
     positions with no self-edge; world topology adjacency is enforced later by
     Task 6 via `VisibleExit` / own-journey edges, not here.
   - `route_edge_pairs(route) -> tuple[tuple[str, str], ...]` returns the
     consecutive **ordered directed** `(from_token, to_token)` pairs in route
     order and rejects a self-edge. Do **not** min/max-sort endpoints; do **not**
     reuse `require_boundary_edges` undirected border semantics.
   - `require_route_edges(value, *, field_name: str) -> tuple[tuple[str, str], ...]`
     accepts only ordered directed pairs, preserves sequence order, rejects
     duplicates that collapse a directed hop, rejects more than 3 edges, and
     never sorts by `(a, b)` or by undirected endpoint pairs. Optional
     publication digests may hash the ordered edge tuple; they must not rewrite
     direction.
   - `migration_location_token(value: EntityId) -> str` and
     `migration_route_tokens(route) -> tuple[str, ...]` are the only
     publication-facing projections; they never emit `EntityId` objects and they
     preserve route order.
   - `migration_candidate_id(kind: str, material: str) -> str` returns
     `mig-` plus the first 32 hex characters of a SHA-256 digest over the
     canonical material; `kind` is closed to `wave`, `cluster`, `outcome`.
   - `migration_publication_id(digest: str) -> str` returns
     `md-pub-` plus the first 32 characters of the digest.
5. Define the frozen dataclasses:
   - `MigrationEvidence`: `kind: MigrationCauseSource`,
     `source_owner_id: AgentId | None`, `source_tick: int`, `lineage_ref: str`,
     `policy_version: str`.
   - `MigrationIntentRow`: `intent_id`, `owner_id`, `origin_location_id`,
     `destination_location_id`, `route_locations`, `cause_ids`, `cluster_ids`,
     `status`, `confidence`, `first_tick`, `last_tick`, `evidence`.
   - `RouteBeliefRow`: `route_id`, `owner_id`, `origin_location_id`,
     `destination_location_id`, `route_locations`, `observed_duration_ticks`,
     `fatigue_cost`, `basis`, `status`, `first_tick`, `last_tick`, `evidence`.
   - `CauseEvidenceRow`: `cause_id`, `owner_id`, `cause_kind`, `source_kind`,
     `anchor_ref: str | None`, `confidence`, `first_tick`, `last_tick`,
     `status`, `evidence`.
   - `SocialClusterBeliefRow`: `cluster_id`, `owner_id`,
     `member_ids: tuple[AgentId, ...]`, `basis`, `confidence`, `status`,
     `first_tick`, `last_tick`, `evidence`.
   - `IntegrationBeliefRow`: `outcome_id`, `owner_id`,
     `destination_location_id`, `domain`, `status`, `confidence`, `first_tick`,
     `last_tick`, `evidence`.
   - `WaveObservationRow`: `observation_id`, `owner_id`, `origin_location_id`,
     `destination_location_id`, `participant_ids`, `cause_ids`, `cluster_ids`,
     `status`, `first_tick`, `last_tick`, `evidence`.
   - `MigrationDisplacementLedger`: `owner_id`, `intents`, `routes`, `causes`,
     `clusters`, `integrations`, `waves`, `notices`, `digest`,
     `policy_version`.
6. In every `__post_init__`, validate owner identity, id shape, ordered and
   unique route locations, sorted and unique id tuples, status enum membership,
   quantized `[0,1]` confidence, non-negative ticks, and `first_tick <=
   last_tick`. Do not resolve an organization, institution, rule, dispute,
   evidence, diplomacy, treaty, conflict, border, or territorial anchor here;
   resolution is an update-pipeline concern.
7. In `src/analysis/migration_displacement_contract.py`, define:
   - `MIGRATION_ANALYSIS_POLICY_VERSION =
     "migration-displacement-analysis.v1"`;
   - `MIGRATION_CANDIDATE_PREFIX = "mig-"`;
   - `MIGRATION_LAYERS` and `MIGRATION_ALIGNMENTS` frozen sets;
   - `MIGRATION_FORBIDDEN_RESULT_FIELDS`;
   - `analysis_migration_candidate_id(kind, material) -> str` using the same
     canonical SHA-256 material as the cognition helper, but importing no
     cognition module.
8. Add `__all__` with every public symbol. Do not export private helpers.
9. Avoid class names `Refugee`, `RefugeeStatus`, `AsylumSeeker`,
   `DisplacedPerson`, `RefugeeCamp`, `ResettlementAuthority`, `MigrationRegistry`,
   `WaveRegistry`, `MigrationWave`, `CauseOracle`, `IntegrationOracle`,
   `AssimilationScore`, `WellbeingScore`, `ForcedMigrationClassifier`,
   `MigrationAuthority`, or `MigrationExecutor`.

### Required Interfaces and Contracts

```python
MIGRATION_DISPLACEMENT_POLICY_VERSION: Final[str] = "migration-displacement.v1"
MIGRATION_DISPLACEMENT_LEDGER_VERSION: Final[str] = "migration-displacement-ledger.v1"
MAX_ROUTE_LOCATIONS: Final[int] = 4
MAX_ROUTE_EDGES: Final[int] = 3

@dataclass(frozen=True, slots=True)
class MigrationIntentRow:
    intent_id: str
    owner_id: AgentId
    origin_location_id: EntityId
    destination_location_id: EntityId
    route_locations: tuple[EntityId, ...]
    cause_ids: tuple[str, ...]
    cluster_ids: tuple[str, ...]
    status: MigrationIntentStatus
    confidence: float
    first_tick: int
    last_tick: int
    evidence: tuple[MigrationEvidence, ...] = ()
```

- A route is **ordered**, **directed**, and **bounded** at 2-4 logical
  locations. Consecutive pairs must be distinct (no self-edge); the contract
  rejects any duplicate location in the sequence. World adjacency is out of
  scope for these helpers.
- Directed hop `A→B` is distinct from `B→A`. Edge helpers must never collapse
  them the way undirected border edges do.
- No field is named `refugee`, `asylum`, `forced`, `displaced`, `threat`,
  `hardship`, `wellbeing`, `assimilation`, `integration_score`, `score`, or
  `composite`.
- A cause is one owner's evidence-backed belief. The contract does not decide
  whether the cause is true.
- Two owners may hold identical intents or routes. Overlap is legal at this
  layer.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — "Extend migration mechanics", "Track origin route
  destination cause evidence family/social clusters integration outcomes",
  "Support migration waves without agents sharing collective telepathy".
- Source: `.ai-factory/ARCHITECTURE.md` — Key Principle 1 and "Memory,
  testimony, and subjective concepts".
- Source: `src/world/regions.py` `RouteSpec`/`Journey`; physics route overrides
  are undirected, but owner route beliefs remain ordered directed location
  sequences.
- Supported combinations: ordered single-hop; 2-4 location route; reverse hop
  retained as distinct; duplicate route; self-edge route; oversized route;
  every case is validated by Task 1 tests before any update exists.

### Error Handling and Logging

- Validation raises `ValueError` with a stable `<field>: <code>` message and
  logs `ERROR migration_displacement_validation_failed field=<field>
  reason_code=<code>`.
- Never log agent ids, origin/destination ids, route ids, cause ids, cluster
  ids, anchors, or evidence refs at INFO or above.
- DEBUG may log counts only: `migration_displacement_contract_constructed
  route_locations=%s causes=%s clusters=%s`.
- Unknown enums fail closed with `unknown_<noun>` codes.

### Tests

- `tests/unit/test_migration_displacement_contract.py`
  - `test_policy_ledger_and_frame_versions_are_frozen`
  - `test_route_locations_preserve_order_and_reject_duplicates`
  - `test_route_requires_two_to_four_locations_and_distinct_consecutive_pairs`
  - `test_route_edges_are_ordered_directed_and_bounded`
  - `test_reverse_directed_hops_are_not_collapsed`
  - `test_intent_validates_owner_route_cause_cluster_status_and_ticks`
  - `test_two_owners_may_hold_identical_or_overlapping_routes`
  - `test_no_forbidden_refugee_or_registry_object_exists`
  - `test_public_tokens_never_emit_entity_objects`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_contract.py -q`
- Expected: all pass.

### Acceptance Criteria

- The module imports with no `world` private authority, no `simulation`,
  `analysis`, `experiments`, `api`, or `persistence` import.
- The route contract is ordered, bounded at 4 locations / 3 edges, and rejects
  duplicates.
- No forbidden class or field exists.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_contract.py -q`
- `uv run --frozen --python 3.12.14 ruff check src/agents/cognition/migration_displacement.py tests/unit/test_migration_displacement_contract.py`
- Expected: pass; no import-linter change yet.

## Task 2: Add the locked migration-displacement cognition and analysis policies

### Intent

Freeze every threshold and cap that an implementer would otherwise choose. The
cognition policy governs how an owner forms and retains migration beliefs; the
analysis policy governs detached wave detection, displacement classification,
cluster detection, and integration outcomes. No policy value is carried in
runner JSON.

### Implementation Steps

1. In `src/agents/cognition/migration_displacement.py`, add
   `MigrationDisplacementPolicy` with exactly these locked defaults and
   `version="migration-displacement.v1"`:
   - `max_intents = 8`
   - `max_route_beliefs = 16`
   - `max_cause_evidence = 32`
   - `max_cluster_beliefs = 8`
   - `max_integration_beliefs = 8`
   - `max_wave_observations = 8`
   - `max_route_locations = 4`
   - `max_cluster_members = 16`
   - `max_evidence_per_row = 16`
   - `max_ledger_rows = 96`
   - `max_intent_age_ticks = 128`
   - `max_route_age_ticks = 256`
   - `max_cause_age_ticks = 256`
   - `max_cluster_age_ticks = 256`
   - `max_integration_age_ticks = 256`
   - `max_wave_age_ticks = 128`
   - `min_intent_confidence = 0.35`
   - `min_cause_support = 1`
   - `max_destination_bias = 0.25`
   - `route_beliefs_observed_only = True`
   - `causes_are_beliefs = True`
   - `intents_bind_commands = False`
   - `clusters_bind_commands = False`
   - `integration_beliefs_are_truth = False`
2. In `src/analysis/migration_displacement_policy.py` add
   `MigrationDisplacementAnalysisPolicy` with
   `version="migration-displacement-analysis.v1"` and exactly:
   - `wave_window_ticks = 12`
   - `max_wave_gap_ticks = 6`
   - `min_wave_participants = 2`
   - `min_wave_distinct_origins = 1`
   - `min_wave_route_overlap = 1`
   - `cause_window_ticks = 16`
   - `min_cause_evidence = 1`
   - `displacement_min_independent_causes = 1`
   - `mixed_min_displacement_causes = 1`
   - `mixed_min_opportunity_causes = 1`
   - `integration_window_ticks = 32`
   - `min_residence_ticks = 4`
   - `cluster_window_ticks = 32`
   - `min_cluster_members = 2`
   - `max_candidates_per_run = 512`
   - `max_pairs_per_run = 4096`
   - `max_rows_per_family = 5000`
   - `quantum = 0.000001`
3. Define `default_migration_displacement_policy()` and
   `default_migration_displacement_analysis_policy()` returning the only
   accepted values.
4. Every policy dataclass rejects any changed numeric value or version with
   `unsupported_policy`, mirroring `BordersPolicy` and `BordersAnalysisPolicy`.
5. Add the policy version to the ledger and to every derived analysis document.
6. Keep `regional-migration-cognition.v1`, `regional-destination-memory.v1`,
   `regional_population@1`, `regional_migration@1`, and
   `regional_destination_beliefs@1` byte-identical; no existing policy constant
   may change.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class MigrationDisplacementPolicy:
    version: str = "migration-displacement.v1"
    max_intents: int = 8
    max_route_beliefs: int = 16
    max_cause_evidence: int = 32
    max_cluster_beliefs: int = 8
    max_integration_beliefs: int = 8
    max_wave_observations: int = 8
    max_route_locations: int = 4
    max_cluster_members: int = 16
    max_evidence_per_row: int = 16
    max_ledger_rows: int = 96
    max_intent_age_ticks: int = 128
    max_route_age_ticks: int = 256
    max_cause_age_ticks: int = 256
    max_cluster_age_ticks: int = 256
    max_integration_age_ticks: int = 256
    max_wave_age_ticks: int = 128
    min_intent_confidence: float = 0.35
    min_cause_support: int = 1
    max_destination_bias: float = 0.25
    route_beliefs_observed_only: bool = True
    causes_are_beliefs: bool = True
    intents_bind_commands: bool = False
    clusters_bind_commands: bool = False
    integration_beliefs_are_truth: bool = False
```

- The booleans are locked policy statements, not switches. A caller cannot set
  `intents_bind_commands=True` and receive a working ledger.
- There is no policy field named `enforce`, `permission`, `refugee`,
  `wellbeing`, `assimilation`, or `score`.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — six cause kinds, origin/route/destination, cause
  evidence, family/social clusters, integration outcomes, waves without
  telepathy.
- Source: `.ai-factory/ARCHITECTURE.md` — "No automatic generalization" and
  "deterministic seeds ... no global RNG"; all thresholds are locked constants.
- Source: `src/agents/cognition/borders.py` `BordersPolicy` and
  `src/analysis/borders_policy.py` for the locked-policy pattern.
- Supported combinations: every cap combination is exercised in Task 2 tests,
  including overflow with and without a droppable row.

### Error Handling and Logging

- Policy construction logs
  `DEBUG migration_displacement_policy_constructed policy_version=%s intents=%s
  routes=%s causes=%s`.
- An unsupported value logs
  `ERROR migration_displacement_policy_rejected field=<field>
  reason_code=unsupported_policy`.
- No runner JSON is read; a missing policy in the loop config is a programming
  error and raises `TypeError` at construction.

### Tests

- `tests/unit/test_migration_displacement_policy.py`
  - `test_policy_versions_and_numbers_are_locked`
  - `test_any_changed_policy_value_is_rejected`
  - `test_policy_helpers_return_the_only_accepted_values`
  - `test_no_command_binding_or_refugee_switch_is_honored`
  - `test_existing_regional_policies_are_unchanged`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_policy.py tests/unit/test_regional_migration_cognition.py -q`
- Expected: all pass.

### Acceptance Criteria

- All policy numbers match the plan exactly.
- No runner schema or per-agent key reads a policy value.
- Existing regional migration policies are unchanged.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_policy.py -q`
- `uv run --frozen --python 3.12.14 pytest tests/unit/test_regional_migration_cognition.py tests/unit/test_regional_demographics.py -q`
- Expected: new tests pass; regional tests unchanged.

## Task 3: Activate migration-displacement cognition on the organizations and regional-migration seam without a new runner schema

### Intent

Make migration-displacement beliefs reachable only when the owned
`organizations` V4 context, the owned `multi_polity_migration` V3 flag, and a
deterministic regional-migration mode are all active. This preserves legacy
v15/v44/v55 behavior and v56's accepted keyset. No new flag, per-agent runner
key, root field, `runner-config-v57`, or capability context is added.

### Implementation Steps

1. In `src/agents/cognition/configuration.py`:
   - Add `class CognitionMigrationDisplacementMode(StrEnum)` with
     `DISABLED = "disabled"` and `DETERMINISTIC = "deterministic"`.
   - Add `migration_displacement_mode:
     CognitionMigrationDisplacementMode = DISABLED` and
     `migration_displacement_policy: MigrationDisplacementPolicy | None = None`
     to `CognitionLoopConfig` after `borders_policy`.
   - In `__post_init__`, validate the mode; when disabled force the policy to
     `None`; when deterministic default it with
     `default_migration_displacement_policy()`; reject any other policy type.
   - Add `"migration_displacement_mode"` and
     `"migration_displacement_policy_version"` to the canonical payload map
     near `"borders_mode"`.
   - In `build_cognitive_loop`, pass `migration_displacement_mode` and
     `migration_displacement_policy` into `CognitiveLoop`.
2. In `src/agents/cognition/loop.py`:
   - Add `_migration_displacement_mode` and
     `_migration_displacement_policy` to `__slots__`.
   - Add constructor keyword arguments `migration_displacement_mode: object |
     None = None` and `migration_displacement_policy: object | None = None`
     after the border arguments.
   - Validate them exactly as border mode/policy are validated. A disabled mode
     forces the policy to `None`; deterministic requires
     `MigrationDisplacementPolicy`.
   - Do not call an updater yet; Task 6 adds
     `_prepare_migration_displacement`.
3. In `src/simulation/runner.py` `_cognition_config_for`:
   - Add keyword arguments `regional_migration_mode: str | None = None` and
     `multi_polity_migration_enabled: bool = False`.
   - After the border derivation, compute:
     ```python
     migration_displacement_mode = (
         CognitionMigrationDisplacementMode.DETERMINISTIC
         if organizations_enabled
         and multi_polity_migration_enabled
         and regional_migration_mode == "deterministic"
         else CognitionMigrationDisplacementMode.DISABLED
     )
     migration_displacement_policy = (
         default_migration_displacement_policy()
         if migration_displacement_mode
         is CognitionMigrationDisplacementMode.DETERMINISTIC
         else None
     )
     ```
   - Pass both into `CognitionLoopConfig` next to `borders_mode`.
   - Log `DEBUG cognition_config_migration_displacement_mode mode=%s
     policy_version=%s organizations=%s multi_polity_migration=%s
     regional_migration_mode=%s`.
   - At all three `_cognition_config_for` call sites, pass
     `regional_migration_mode=(None if config.regions_migration is None else
     config.regions_migration.cognition_mode.value)` and
     `multi_polity_migration_enabled=(
     config.v3_capability_flags.multi_polity_migration)`.
   - Do not rely solely on the v44 gate to imply the V3 flag; require it
     explicitly even if a regional object is somehow present.
   - Do not add a runner model field, serialization key, compatibility branch, or
     schema version.
4. In `src/agents/cognition/__init__.py` and
   `src/simulation/cognition_contracts.py`, export
   `CognitionMigrationDisplacementMode`, `MigrationDisplacementPolicy`,
   `default_migration_displacement_policy`, and the row types from Task 1.
5. Leave `src/agents/cognition/architectures.py` unchanged except for the
   `CognitionLoopConfig` default. A composed architecture snapshot has no
   migration-displacement mode and therefore stays disabled. Add a test
   asserting that.
6. Do not add a prerequisite gate in `simulation.runner`. Migration-displacement
   beliefs are an internal extension of `organizations` and the owned V3
   migration seam; they do not require `diplomacy`, `organized_conflict`,
   `formal_rules`, or any institution/office mode. Missing anchors stay
   unresolved. `organizations` is the opt-in V4 context because it already owns
   the institution and social-cluster beliefs a migration cause may reference;
   it is not a claim that migration requires an organization.

### Required Interfaces and Contracts

```python
class CognitionMigrationDisplacementMode(StrEnum):
    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"

@dataclass(frozen=True, slots=True)
class CognitionLoopConfig:
    ...
    migration_displacement_mode: CognitionMigrationDisplacementMode = (
        CognitionMigrationDisplacementMode.DISABLED
    )
    migration_displacement_policy: MigrationDisplacementPolicy | None = None
```

- Activation matrix:
  | Runner | `multi_polity_migration` | `organizations` | regional cognition | Migration mode |
  | --- | --- | --- | --- | --- |
  | v15/v44/v55 | any | not available | deterministic | disabled |
  | v56 | off | on | deterministic | disabled (v44 gate rejects) |
  | v56 | on | off | deterministic | disabled |
  | v56 | on | on | absent | disabled |
  | v56 | on | on | disabled | disabled |
  | v56 | on | on | deterministic | deterministic |
- No `runner-config-v57` constant, no new `v4_capability_flags` key, no new
  `AgentCognitionSpec` key, and no new `SimulationRunnerConfig` root field.
- `CognitionLoopConfig` remains an internal factory value. A changed default
  preserves existing architecture behavior; a composed snapshot without the new
  mode stays disabled.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — "Extend migration mechanics for population-scale
  movement".
- Source: `.ai-factory/ARCHITECTURE.md` — "Capability ownership" lists
  `organizations` as owned and says per-agent modes are not automatic flags;
  "Versioned Extension Contract" requires accepted-set evolution.
- Source: `src/simulation/runner_models.py` `multi_polity_migration` 1091 and
  v44/v56 gates 9379-9425, 9653-9685.
- Supported combinations: the six rows above are each tested, plus another
  unowned V4 flag still fails closed.

### Error Handling and Logging

- A wrong `migration_displacement_mode` type raises
  `TypeError("migration_displacement_mode must be
  CognitionMigrationDisplacementMode")`.
- A deterministic mode with a wrong policy raises
  `TypeError("migration_displacement_policy must be
  MigrationDisplacementPolicy")`.
- Disabled mode logs `DEBUG cognition_migration_displacement_mode disabled`.
- Activation logs counts/booleans only; never agent ids, locations, routes, or
  cause contents.
- A missing `organizations` flag or non-deterministic regional mode is not an
  error; it is a disabled passthrough.

### Tests

- `tests/unit/test_migration_displacement_activation.py`
  - `test_v56_organizations_and_deterministic_regional_mode_enable_migration`
  - `test_v56_without_organizations_stays_disabled`
  - `test_v56_without_multi_polity_migration_stays_disabled`
  - `test_v56_without_regions_migration_stays_disabled`
  - `test_v56_with_regional_cognition_disabled_stays_disabled`
  - `test_v15_v44_v55_are_unchanged`
  - `test_architectures_compose_migration_displacement_disabled_by_default`
  - `test_cognition_factory_version_stays_v1_and_payload_includes_migration`
  - `test_no_runner_v57_or_new_flag_key_exists`
  - `test_existing_unowned_v4_flag_still_fails_closed`
  - `test_diplomacy_conflict_and_rules_are_not_required`
- Commands:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_activation.py tests/unit/test_runner_config_v44.py tests/unit/test_runner_config_v56.py tests/unit/test_v4_scaffolding_gate.py -q`
- Expected: all pass; no schema pin changes.

### Acceptance Criteria

- Migration-displacement cognition activates only under v56 + `organizations` +
  `multi_polity_migration` + deterministic regional migration.
- No new runner schema, flag, context, root field, or per-agent runner key exists.
- The v56 accepted keyset and all default-off legacy paths are unchanged.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_migration_displacement_activation.py -q`
- `uv run --frozen --python 3.12.14 pytest tests/unit/test_runner_config_v44.py tests/unit/test_runner_config_v56.py tests/unit/test_v4_scaffolding_gate.py tests/unit/test_runner_config_v4_flags.py -q`
- `rg -n "runner-config-v57|v4_capability_flags.*migration|migration.*V4CapabilityFlags" src tests docs` — expected: no matches.
- Expected: all pass.

## Phase Risks and Mitigations

- Risk: a new internal mode leaks into runner JSON and becomes an unplanned schema
  key.
  Mitigation: Task 3 tests assert the v56 exact keyset and `v57` absence; no
  runner model/serializer field is added.
- Risk: extending regional migration changes legacy v44 behavior.
  Mitigation: migration-displacement mode is derived only when `organizations`
  is on; v15/v44/v55 stay disabled.
- Risk: a route is confused with a region or a grid.
  Mitigation: only ordered `EntityId` locations and consecutive adjacency pairs;
  no region-derived membership, coordinates, polygons, or area fields.
- Risk: the word "migration" collides with Alembic schema migration.
  Mitigation: module and env names use `migration_displacement`, and docs state
  that this is population movement, not SQL migration.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
