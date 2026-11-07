# Phase 1: Border Contract and Seam

Plan: [index.md](index.md)
Tasks: 1-3
Depends on: none

## Objective

Freeze the closed territorial-domain vocabulary, the location-set and
boundary-edge contracts, the locked cognition and analysis policies, and the
activation rule that makes border beliefs available only when the owned
`organizations` context and deterministic territorial claims are both active.
This phase adds no runner schema, flag, context, command, event, write pair, API
version, or migration.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/agents/cognition/territorial.py` | `TerritorialClaimLedger` 313-361; `TerritorialClaim` 252-310; `ClaimTargetKind` 62-69; `TERRITORIAL_CLAIM_POLICY_VERSION` 35 | Existing single-location owner belief that the set model must extend without rewriting |
| `src/agents/cognition/territorial.py` | `apply_territorial_update` 975-1072; `territorial_wait_replacement` 1221-1378 | Existing update and command-replacement patterns; border beliefs add no command path |
| `src/agents/cognition/configuration.py` | `CognitionTerritorialClaimMode` 323-331; `CognitionLoopConfig` 604-760; `build_cognitive_loop` 1724-1965 | Internal cognition configuration seam; no runner key is added |
| `src/simulation/runner.py` | `_cognition_config_for` 1030-1660; `organizations_enabled` parameter 1034-1041; territorial mode 1187-1195 | Existing per-agent derivation point for an internal border mode |
| `src/simulation/v4_architecture.py` | `V4ContextId` 60-76; `ORGANIZATIONS` 110-127; diplomacy non-goal 156-169 | 14 contexts / 12 flags are closed; no new context or flag |
| `src/simulation/runner_models.py` | `V4CapabilityFlags` 1130-1145; exact-key validation 305-326 | `organizations` is already owned; v56 remains the only V4 schema |
| `src/simulation/compatibility.py` | owned V4 flag mirrors 130-160 | Ownership pins must stay consistent |
| `src/world/regions.py` | `RegionDefinition` 39-49; `LocationRegion` 51-61; `RouteSpec` 64-99; `RegionsMigrationSpec` 102-224 | Regions are logical labels over locations; no geometry or ownership |
| `src/world/models.py` | `Location` 81-111; `AgentBody` 189-229 | WorldEngine knows locations, adjacency, capacity, and occupancy only |
| `src/world/observations.py` | `Observation.location` 1300-1326; `VisibleExit` 284-330 | An owner can observe its current location and adjacent exits for local boundary edges |
| `src/analysis/spatial_control_metrics.py` | `SpatialActionRow` 83-93; `SpatialClaimRow` 95-103; `compute_spatial_control` 114-186 | Existing detached physical-control analysis remains unchanged |
| `src/analysis/diplomacy_contract.py` | forbidden result fields 73-96; layer enums 121-147 | Pattern for a closed, non-truth analysis vocabulary |
| `src/analysis/organized_conflict_contract.py` | forbidden fields 35-50; closed enums 53-91 | Newest V4 analysis contract pattern |
| `tests/architecture/test_v4_architecture_invariants.py` | registry and pin assertions | Must remain green; no context count change |
| `tests/architecture/test_treaty_boundaries.py` | forbidden classes 35-51 include `Border` | The new code must not define a class named exactly `Border` |
| `tests/unit/test_territorial_claims.py` | v15 round trip 291; policy locks 161; ledger invariants 264 | Existing territory behavior must stay byte-compatible |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/agents/cognition/borders.py` | create | Closed border vocabulary, locked policy, location-set and boundary-edge contracts, IDs, ledger rows |
| `src/analysis/borders_contract.py` | create | Closed detached-analysis vocabulary, forbidden result fields, layer and alignment enums |
| `src/analysis/borders_policy.py` | create | Locked analysis thresholds and bounded row budgets |
| `src/agents/cognition/configuration.py` | modify | Add internal `CognitionBordersMode`; add `borders_mode`/`borders_policy` to `CognitionLoopConfig`; canonical payload keys |
| `src/simulation/runner.py` | modify | Derive border mode from `organizations_enabled` and deterministic territorial mode |
| `src/agents/cognition/loop.py` | modify | Accept and store the internal border mode/policy; no update call yet |
| `src/agents/cognition/__init__.py` | modify | Export the new public border symbols |
| `src/simulation/cognition_contracts.py` | modify | Re-export the internal border mode for the simulation layer |
| `tests/unit/test_borders_contract.py` | create | Vocabulary, ID, location-set, boundary-edge, and forbidden-name tests |
| `tests/unit/test_borders_policy.py` | create | Locked policy and unsupported-policy tests |
| `tests/unit/test_borders_activation.py` | create | Activation combinations, v57 absence, no runner key |

## Task 1: Freeze the territorial-domain vocabulary, identifier grammar, and location-set contract

### Intent

Define the closed nouns that every later phase uses. A domain is one owner's
belief about a set of logical `EntityId` locations, not a world object, not a
polygon, not a grid cell, and not a country. Boundary edges are ordered pairs of
logical location ids inferred from observed adjacency, never geometric segments.

### Implementation Steps

1. Create `src/agents/cognition/borders.py` with a module docstring that states:
   - one owner's belief only;
   - `WorldEngine`, perception, admission, stop selectors, memory, prompts,
     observer semantics, and Godot never read it;
   - no objective owner, country, border, grid, polygon, or registry exists;
   - no helper returns, constructs, submits, resolves, or blocks a command.
2. Add the constants:
   - `BORDERS_POLICY_VERSION: Final[str] = "borders-claims.v1"`
   - `BORDERS_LEDGER_VERSION: Final[str] = "borders-ledger.v1"`
3. Add closed enums:
   - `DomainClaimStatus`: `claimed`, `recognized`, `disputed`, `withdrawn`,
     `expired`, `unknown`.
   - `BoundaryBasis`: `own_claim`, `direct_observation`, `testimony`,
     `agreement`, `unresolved`.
   - `BoundaryStatus`: `recognized`, `unresolved`, `disputed`.
   - `AccessExpectationMode`: `open`, `restricted`, `permission_expected`,
     `unknown`.
   - `AccessSubjectKind`: `self_agent`, `other_agent`, `organization`,
     `unknown`.
   - `CounterpartyKind`: `agent`, `organization`, `settlement`, `unknown`.
   - `AgreementAct`: `claim_domain`, `propose`, `accept`, `reject`, `withdraw`,
     `recognize`, `expect_access`, `dispute_domain`.
   - `AgreementStatus`: `proposed`, `apparent_acceptance`, `recognized`,
     `disputed`, `withdrawn`, `expired`, `superseded`.
   - `AgreementProvision`: `passage`, `non_entry`, `shared_use`,
     `territorial_acknowledgement`, `unknown`.
   - `BorderNoticeCode`: `unresolved_anchor`, `overlap_detected`,
     `boundary_unobserved`, `domain_cap_reached`, `agreement_cap_reached`,
     `access_cap_reached`, `dispute_cap_reached`, `evidence_cap_reached`,
     `ledger_cap_reached`, `truncated`, `malformed_frame`, `peer_claim_untrusted`.
4. Define the pure value helpers:
   - `require_location_set(value: object, *, field_name: str) -> tuple[EntityId, ...]`
     accepts only an ordered sequence of exact `EntityId`, rejects
     strings/bytes/sets/mappings, deduplicates only by rejecting duplicates,
     sorts by `.value`, requires `1 <= len <= 8`, and rejects a location equal to
     itself only through duplicate detection.
   - `boundary_edge(a: EntityId, b: EntityId) -> tuple[str, str]` returns the
     canonical sorted pair and rejects `a == b` with `boundary_self_edge`.
   - `require_boundary_edges(value: object, *, field_name: str) -> tuple[tuple[str, str], ...]`
     accepts only canonical pairs, sorts by `(a, b)`, rejects duplicates and
     more than 32 edges.
   - `domain_location_tokens(domain) -> tuple[str, ...]` and
     `domain_edge_tokens(domain) -> tuple[tuple[str, str], ...]` are the only
     publication-facing projections; they never emit `EntityId` objects.
5. Define the frozen dataclasses at this stage only as far as the vocabulary
   needs them:
   - `BorderEvidence`: `kind: BoundaryBasis`, `source_owner_id: AgentId | None`,
     `source_tick: int`, `lineage_ref: str`, `policy_version: str`.
   - `TerritorialDomainClaim`: `domain_id`, `owner_id`, `location_ids`,
     `boundary_edges`, `anchor_kind: str | None`, `anchor_ref: str | None`,
     `status: DomainClaimStatus`, `strength: float`, `first_tick`, `last_tick`,
     `evidence`.
   - `BoundaryRecognition`: `domain_id`, `boundary_edges`, `basis`,
     `status`, `evidence`.
   - `AccessExpectation`: `expectation_id`, `domain_id`,
     `subject_kind`, `subject_ref: str | None`, `mode`, `status`, `evidence`.
   - `BorderAgreement`: `agreement_id`, `domain_id`, `counterparty_kind`,
     `counterparty_ref`, `provisions`, `status`, `recognition`,
     `effective_tick`, `expiry_tick`, `evidence`.
   - `BorderDispute`: `dispute_id`, `domain_id`, `counterparty_kind`,
     `counterparty_ref`, `contested_location_ids`, `status`, `evidence`.
   - `BorderLedger`: `owner_id`, `domains`, `recognitions`, `access_expectations`,
     `agreements`, `disputes`, `notices`, `digest`, `policy_version`.
6. In every `__post_init__`, validate owner identity, id shape, sorted and
   unique location/edge tuples, status enum membership, quantized `[0,1]`
   strength, non-negative ticks, `effective_tick <= expiry_tick` when both are
   present, and the row caps from Task 2. Do not resolve an organization or
   diplomacy anchor here; resolution is an update-pipeline concern.
7. Add `__all__` with every public symbol. Do not export private helpers.
8. Avoid a class named exactly `Border`. Use `TerritorialDomainClaim`,
   `BoundaryRecognition`, `BorderAgreement`, `BorderDispute`, `BorderLedger`.
   No `CountryOwner`, `Sovereignty`, `TerritoryRegistry`, `BorderRegistry`, or
   `BorderAuthority` class exists.

### Required Interfaces and Contracts

```python
BORDERS_POLICY_VERSION: Final[str] = "borders-claims.v1"
MAX_LOCATIONS_PER_DOMAIN: Final[int] = 8
MAX_BOUNDARY_EDGES_PER_DOMAIN: Final[int] = 32

@dataclass(frozen=True, slots=True)
class TerritorialDomainClaim:
    domain_id: str
    owner_id: AgentId
    location_ids: tuple[EntityId, ...]
    boundary_edges: tuple[tuple[str, str], ...]
    anchor_kind: str | None
    anchor_ref: str | None
    status: DomainClaimStatus
    strength: float
    first_tick: int
    last_tick: int
    evidence: tuple[BorderEvidence, ...] = ()
```

- `anchor_kind` is closed to `organization`, `settlement`, `agent`, `unknown`,
  or `None`; `anchor_ref` is required for every non-`unknown`/non-`None` kind
  and is bounded to 128 characters.
- A location set is unordered input, sorted output. Two owners may hold the same
  set; two domains of one owner may overlap. Overlap is legal at this layer.
- Boundary edges are **observed** adjacency pairs. Their absence is never proof
  that no border exists.
- No field is named `border`, `country`, `owner_country`, `sovereign`,
  `legitimate`, `winner`, `score`, or `composite`.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — "Extend V3 territoriality to sets of logical
  Locations", "No grid conversion", "No objective CountryOwner field".
- Source: `.ai-factory/ARCHITECTURE.md` — Key Principle 1 (objective state,
  owner belief, analysis are different authorities) and "Memory, testimony, and
  subjective concepts".
- Source: `src/world/models.py` `Location` and `src/world/regions.py`
  `RegionDefinition`/`LocationRegion`; the contract uses only logical ids and
  observed adjacency.
- Supported combinations: one location; multiple contiguous locations; multiple
  non-contiguous locations; overlapping owners; empty/unobserved boundary; all
  are validated by Task 1 tests before any update exists.

### Error Handling and Logging

- Validation raises `ValueError` with a stable `<field>: <code>` message and
  logs `ERROR borders_validation_failed field=<field> reason_code=<code>`.
- Never log location ids, owner ids, anchors, or evidence refs at INFO or above.
- DEBUG may log counts only: `borders_contract_constructed locations=%s edges=%s`.
- Unknown enums fail closed with `unknown_<noun>` codes.

### Tests

- `tests/unit/test_borders_contract.py`
  - `test_policy_and_ledger_versions_are_frozen`
  - `test_location_set_rejects_strings_sets_duplicates_and_oversize`
  - `test_boundary_edge_is_canonical_and_rejects_self_edge`
  - `test_boundary_edges_reject_duplicates_and_oversize`
  - `test_domain_claim_validates_owner_anchor_status_strength_and_ticks`
  - `test_two_owners_may_hold_identical_or_overlapping_sets`
  - `test_no_forbidden_object_or_class_name_exists`
  - `test_public_tokens_never_emit_entity_objects`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_contract.py -q`
- Expected: all pass.

### Acceptance Criteria

- The module imports with no `world` private authority, no `simulation`,
  `analysis`, `experiments`, `api`, or `persistence` import.
- The location-set and edge contracts are deterministic, sorted, deduplicated by
  rejection, and bounded at 8 locations and 32 edges.
- No forbidden class or field exists.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_contract.py -q`
- `uv run --frozen --python 3.12.14 ruff check src/agents/cognition/borders.py tests/unit/test_borders_contract.py`
- Expected: pass; no import-linter change yet.

## Task 2: Add the locked border cognition and analysis policies

### Intent

Freeze every threshold and cap that an implementer would otherwise choose. The
cognition policy governs how an owner forms and retains beliefs; the analysis
policy governs detached overlap, recognition, and control-pattern classification.
No policy value is carried in runner JSON.

### Implementation Steps

1. In `src/agents/cognition/borders.py`, add `BordersPolicy` with exactly these
   locked defaults and a `version="borders-claims.v1"`:
   - `min_claim_strength = 0.40`
   - `max_domains = 8`
   - `max_locations_per_domain = 8`
   - `max_boundary_edges_per_domain = 32`
   - `max_agreements = 8`
   - `max_access_expectations = 16`
   - `max_disputes = 8`
   - `max_evidence_per_row = 32`
   - `max_ledger_rows = 128`
   - `max_domain_evidence_age_ticks = 256`
   - `max_agreement_age_ticks = 128`
   - `min_recognition_parties = 2`
   - `agreement_acceptance_min_parties = 2`
   - `overlap_min_locations = 1`
   - `domain_contiguity_required = True`
   - `boundary_edges_observed_only = True`
   - `access_expectations_bind_commands = False`
   - `agreements_bind_commands = False`
2. In `src/analysis/borders_policy.py` add `BordersAnalysisPolicy` with
   `version="borders-analysis.v1"` and exactly:
   - `physical_window_ticks = 6`
   - `min_use_actions = 2`
   - `min_distinct_actors = 2`
   - `hostile_window_ticks = 6`
   - `overlap_min_claim_strength = 0.40`
   - `recognition_min_declarations = 1`
   - `agreement_consistency_min_parties = 2`
   - `control_pattern_window_ticks = 12`
   - `control_pattern_min_physical_actions = 2`
   - `max_pairs_per_run = 4096`
   - `max_rows_per_family = 5000`
   - `quantum = 0.000001`
3. Define `default_borders_policy()` and
   `default_borders_analysis_policy()` returning the only accepted values.
4. Every policy dataclass rejects any changed numeric value or version with
   `unsupported_policy`, mirroring `TerritorialClaimPolicy` 364-437.
5. Add the policy version to the ledger and to every derived analysis document.
6. Keep `territorial-claims.v1`, `spatial_control@1`, and
   `territorial_concentration@1` byte-identical; no existing policy constant may
   change.

### Required Interfaces and Contracts

```python
@dataclass(frozen=True, slots=True)
class BordersPolicy:
    version: str = "borders-claims.v1"
    min_claim_strength: float = 0.40
    max_domains: int = 8
    max_locations_per_domain: int = 8
    max_boundary_edges_per_domain: int = 32
    max_agreements: int = 8
    max_access_expectations: int = 16
    max_disputes: int = 8
    max_evidence_per_row: int = 32
    max_ledger_rows: int = 128
    max_domain_evidence_age_ticks: int = 256
    max_agreement_age_ticks: int = 128
    min_recognition_parties: int = 2
    agreement_acceptance_min_parties: int = 2
    overlap_min_locations: int = 1
    domain_contiguity_required: bool = True
    boundary_edges_observed_only: bool = True
    access_expectations_bind_commands: bool = False
    agreements_bind_commands: bool = False
```

- The booleans are locked policy statements, not switches. A caller cannot set
  `access_expectations_bind_commands=True` and receive a working ledger.
- There is no policy field named `enforce`, `permission`, `sovereignty`, or
  `score`.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — claims, overlapping claims, disputed borders,
  recognized boundaries, access expectations, border agreements.
- Source: `.ai-factory/ARCHITECTURE.md` — "No automatic generalization" and
  "deterministic seeds ... no global RNG"; all thresholds are locked constants.
- Source: `src/agents/cognition/territorial.py` 364-437 for the locked-policy
  pattern.
- Supported combinations: every cap combination is exercised in Task 2 tests,
  including overflow with and without a droppable row.

### Error Handling and Logging

- Policy construction logs
  `DEBUG borders_policy_constructed policy_version=%s domains=%s locations=%s`.
- An unsupported value logs
  `ERROR borders_policy_rejected field=<field> reason_code=unsupported_policy`.
- No runner JSON is read; a missing policy in the loop config is a programming
  error and raises `TypeError` at construction.

### Tests

- `tests/unit/test_borders_policy.py`
  - `test_policy_versions_and_numbers_are_locked`
  - `test_any_changed_policy_value_is_rejected`
  - `test_policy_helpers_return_the_only_accepted_values`
  - `test_no_command_binding_switch_is_honored`
- Commands: `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_policy.py -q`
- Expected: all pass.

### Acceptance Criteria

- All policy numbers match the plan exactly.
- No runner schema or per-agent key reads a policy value.
- Existing territorial and spatial-control policies are unchanged.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_policy.py tests/unit/test_territorial_claims.py -q`
- Expected: new tests pass; territorial tests unchanged.

## Task 3: Activate border cognition on the organizations seam without a new runner schema

### Intent

Make border beliefs reachable only when the owned `organizations` V4 context and
an agent's deterministic territorial-claim mode are both active. This preserves
legacy v15/v44/v55 behavior and v56's accepted keyset. No new flag, per-agent
runner key, root field, `runner-config-v57`, or capability context is added.

### Implementation Steps

1. In `src/agents/cognition/configuration.py`:
   - Add `class CognitionBordersMode(StrEnum)` with `DISABLED = "disabled"` and
     `DETERMINISTIC = "deterministic"`.
   - Add `borders_mode: CognitionBordersMode = CognitionBordersMode.DISABLED`
     and `borders_policy: BordersPolicy | None = None` to `CognitionLoopConfig`
     after `territorial_claim_policy`.
   - In `__post_init__`, validate the mode; when disabled force the policy to
     `None`; when deterministic default it with `default_borders_policy()`;
     reject any other policy type.
   - Add `"borders_mode"` and `"borders_policy_version"` to the canonical payload
     map near `"territorial_claim_mode"` (current line 1562).
   - In `build_cognitive_loop`, pass `borders_mode=resolved.borders_mode` and
     `borders_policy=resolved.borders_policy` into `CognitiveLoop`.
2. In `src/agents/cognition/loop.py`:
   - Add `_borders_mode` and `_borders_policy` to `__slots__`.
   - Add constructor keyword arguments `borders_mode: object | None = None` and
     `borders_policy: object | None = None` after the territorial arguments.
   - Validate them exactly as territorial mode/policy are validated at
     lines 708-725. A disabled mode forces the policy to `None`; deterministic
     requires `BordersPolicy`.
   - Do not call an updater yet; Task 6 adds `_prepare_borders`.
3. In `src/simulation/runner.py` `_cognition_config_for`:
   - `organizations_enabled` already exists at line 1034.
   - After `territorial_mode` is resolved at 1187, compute:
     ```python
     borders_mode = (
         CognitionBordersMode.DETERMINISTIC
         if organizations_enabled
         and territorial_mode is CognitionTerritorialClaimMode.DETERMINISTIC
         else CognitionBordersMode.DISABLED
     )
     borders_policy = (
         default_borders_policy()
         if borders_mode is CognitionBordersMode.DETERMINISTIC
         else None
     )
     ```
   - Pass `borders_mode` and `borders_policy` into `CognitionLoopConfig` next to
     `territorial_claim_mode`.
   - Log `DEBUG cognition_config_borders_mode mode=%s policy_version=%s
     organizations=%s territorial_mode=%s`.
   - Do not add a runner model field, serialization key, compatibility branch, or
     schema version.
4. In `src/agents/cognition/__init__.py` and
   `src/simulation/cognition_contracts.py`, export
   `CognitionBordersMode`, `BordersPolicy`, `default_borders_policy`, and the row
   types from Task 1.
5. Leave `src/agents/cognition/architectures.py` unchanged except for the
   `CognitionLoopConfig` default. A composed architecture snapshot has no border
   mode and therefore stays disabled. Add a test asserting that.
6. Do not add a prerequisite gate in `simulation.runner`. Border beliefs are an
   internal extension of `organizations`; they do not require `diplomacy`.
   Agreement anchors that reference a treaty remain unresolved when the
   diplomacy ledger is absent.

### Required Interfaces and Contracts

```python
class CognitionBordersMode(StrEnum):
    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"

@dataclass(frozen=True, slots=True)
class CognitionLoopConfig:
    ...
    borders_mode: CognitionBordersMode = CognitionBordersMode.DISABLED
    borders_policy: BordersPolicy | None = None
```

- Activation matrix:
  | Runner | `organizations` | territorial mode | Border mode |
  | --- | --- | --- | --- |
  | v4/v15/v44/v55 | any | deterministic | disabled |
  | v56 | off | deterministic | disabled |
  | v56 | on | disabled | disabled |
  | v56 | on | deterministic | deterministic |
- No `runner-config-v57` constant, no new `v4_capability_flags` key, no new
  `AgentCognitionSpec` key, and no new `SimulationRunnerConfig` root field.
- `CognitionLoopConfig` remains an internal factory value. A changed default
  preserves all existing architecture snapshots.

### Requirement Evidence (when reconciliation applies)

- Source: Original Request — "Extend V3 territoriality", "Agents/organizations
  may believe".
- Source: `.ai-factory/ARCHITECTURE.md` — "Capability ownership" lists
  `organizations` as owned and says per-agent modes are not automatic flags;
  "Versioned Extension Contract" requires accepted-set evolution.
- Source: `src/simulation/v4_architecture.py` 14 contexts / 12 flags; no border
  context exists.
- Supported combinations: the four rows above are each tested, plus another
  unowned V4 flag still fails closed.

### Error Handling and Logging

- A wrong `borders_mode` type raises
  `TypeError("borders_mode must be CognitionBordersMode")`.
- A deterministic mode with a wrong policy raises
  `TypeError("borders_policy must be BordersPolicy")`.
- Disabled mode logs `DEBUG cognition_borders_mode disabled`.
- Activation logs counts/booleans only; never agent ids or claim contents.
- A missing `organizations` flag is not an error; it is a disabled passthrough.

### Tests

- `tests/unit/test_borders_activation.py`
  - `test_v56_organizations_and_territorial_mode_enable_borders`
  - `test_v56_without_organizations_stays_disabled`
  - `test_v56_without_territorial_mode_stays_disabled`
  - `test_v15_v44_v55_are_unchanged`
  - `test_architectures_compose_borders_disabled_by_default`
  - `test_cognition_factory_version_stays_v1_and_payload_includes_borders`
  - `test_no_runner_v57_or_new_flag_key_exists`
  - `test_existing_unowned_v4_flag_still_fails_closed`
  - `test_diplomacy_is_not_required_for_border_cognition`
- Commands:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_activation.py tests/unit/test_runner_config_v56.py tests/unit/test_v4_scaffolding_gate.py -q`
- Expected: all pass; no schema pin changes.

### Acceptance Criteria

- Border cognition activates only under v56 + `organizations` + deterministic
  territorial mode.
- No new runner schema, flag, context, root field, or per-agent runner key exists.
- The v56 accepted keyset and all default-off legacy paths are unchanged.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_borders_activation.py -q`
- `uv run --frozen --python 3.12.14 pytest tests/unit/test_runner_config_v56.py tests/unit/test_v4_scaffolding_gate.py tests/unit/test_runner_config_v4_flags.py -q`
- `rg -n "runner-config-v57|v4_capability_flags.*borders|borders.*V4CapabilityFlags" src tests docs` — expected: no matches.
- Expected: all pass.

## Phase Risks and Mitigations

- Risk: a new internal mode leaks into runner JSON and becomes an unplanned schema
  key.
  Mitigation: Task 3 tests assert the v56 exact keyset and `v57` absence; no
  runner model/serializer field is added.
- Risk: extending territorial claims changes legacy v15 behavior.
  Mitigation: border mode is derived only when `organizations` is on; v15/v44/v55
  stay disabled.
- Risk: the word "border" collides with the existing forbidden class-name test.
  Mitigation: no class named exactly `Border`; the boundary test scans for the
  exact forbidden set and the new names are documented.
- Risk: a location set is confused with a region or a grid.
  Mitigation: only `EntityId` locations and observed adjacency pairs; no
  region-derived membership, coordinates, polygons, or area fields.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
