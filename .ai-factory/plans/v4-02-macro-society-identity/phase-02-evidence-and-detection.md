# Phase 2: Evidence and Candidate Detection

Plan: [index.md](index.md)
Tasks: 3-5
Depends on: Phase 1 (Tasks 1-2)

## Objective

Turn detached evidence from nine lanes into normalized analysis windows, detect
large society-like clusters per lane, and compose overlapping cross-lane
candidates with explicit fragmentation and contention status — while keeping
objective population structure, owner-scoped identity claims, and the analytical
candidate in three separate representations.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/analysis/society_emergence.py` | `_person_of` (273), `_normalize_residence` (281), `_normalize_edges` (306), `compute_candidate_communities` (354) | Duck-typed normalization and per-window clustering pattern to mirror. |
| `src/analysis/society_emergence.py` | `SocietyEmissionResult.__post_init__` (221-270) | Current exclusive-membership rule that V4-02 must not reuse. |
| `src/analysis/network_metrics.py` | `canonicalize_community_labels` | Deterministic community label canonicalization. |
| `src/analysis/numerical.py` | `SUPPORTED_COMMUNITY_ALGORITHM`, `sorted_graph_nodes`, `quantize_float`, `require_finite` | Pinned algorithm and deterministic ordering helpers. |
| `src/analysis/group_formation_metrics.py` | `_JACCARD = 0.5` (53), `compute_group_persistence` (127) | Existing adjacent-window Jaccard comparison. |
| `src/analysis/collective_decisions.py` | `CollectiveProposalRow`, `CollectivePositionRow` (`owner_id`, `proposal_ref`) | Self-identification/collective-decision lane inputs. |
| `src/analysis/institutional_decay.py` | `InstitutionTemporalRow` (`owner_id`, `local_pattern_id`, `office_id`, `observation_tick`) | Institution lane inputs. |
| `src/analysis/cultural_trait_dynamics.py` | `BoundaryTraitState` (`living_owner_ids`, `carriers`) | Culture lane inputs. |
| `src/analysis/structured_commitments.py` | `CommitmentItemMove`, `CommitmentLedgerSnapshot` | Exchange lane inputs. |
| `src/analysis/society_isolation.py` | `SocietyJourneyRow` (85) | Migration lane inputs. |
| `src/analysis/spatial_control_metrics.py` | `SpatialClaimRow` (`owner_id`, `target_kind`, `target_entity_id`) | Territory lane inputs. |
| `src/analysis/cultural_evolution_evidence.py` | `GroupMembership` (`owner_id`, `group_id`, `basis_id`) | Self-identification token inputs. |
| `src/analysis/regional_population.py` | `RegionalHistory`, `RegionalLocationRow`, `compute_regional_population` | Objective population structure source (reuse, never recompute). |
| `src/world/observations.py` | `ObservedCommunication` (`speaker_id`, `listener_id`, `action_kind`) | Communication lane inputs. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/analysis/macro_society_evidence.py` | create | Edge/token/window types plus per-lane adapters. |
| `src/analysis/macro_society_detection.py` | create | Per-lane clustering and cross-lane candidate composition. |
| `src/analysis/macro_society_layers.py` | create | Objective/subjective/analytical layer projection with leakage checks. |
| `src/analysis/__init__.py` | modify | Export new names. |
| `tests/unit/test_macro_society_evidence.py` | create | Adapter and validation proofs. |
| `tests/unit/test_macro_society_detection.py` | create | Clustering, overlap, fragmentation, contention proofs. |
| `tests/unit/test_macro_society_layers.py` | create | Three-layer separation and leakage proofs. |

## Task 3: Normalize detached evidence into analysis windows

### Intent

Every later stage consumes one normalized shape, so lane-specific row formats,
version drift, and missing evidence are handled once. Adapters are read-only
projections: they never import the engine, never copy private content, and never
invent identifiers.

### Implementation Steps

1. Create `src/analysis/macro_society_evidence.py` importing only the standard
   library, `analysis.macro_society_contract`, `world.identifiers`, and
   `analysis.numerical`.
2. Define `@dataclass(frozen=True, slots=True) class MacroSocietyEdge` with
   `lane: MacroSocietyLane`, `source_person_id`, `target_person_id`, `tick`,
   `weight: float = 1.0`. Validation: lane must be in `EDGE_LANES`
   (`macro_society_unknown_lane`), no self edges
   (`macro_society_self_edge_rejected`), finite positive weight
   (`macro_society_invalid_weight`), non-negative tick.
3. Define `@dataclass(frozen=True, slots=True) class MacroSocietyToken` with
   `lane: MacroSocietyLane`, `person_id`, `token_id`. Validation: lane must be
   in `TOKEN_LANES`, `token_id` is an opaque stable id, one person may hold
   several tokens in the same lane (that is how overlapping identities arise).
4. Define `@dataclass(frozen=True, slots=True) class MacroSocietyWindowEvidence`
   with `window_index: int`, `tick_start: int`, `tick_end: int`,
   `person_ids: tuple[str, ...]`, `edges: tuple[MacroSocietyEdge, ...]`,
   `tokens: tuple[MacroSocietyToken, ...]`. Validation: window index
   non-negative, `tick_end >= tick_start`, sorted unique person ids, every edge
   endpoint and token person present in `person_ids`
   (`macro_society_unknown_person`), bounded by `MAX_WINDOW_PERSONS` /
   `MAX_WINDOW_EDGES` / `MAX_EVIDENCE_WINDOWS` with
   `macro_society_window_too_large`, edges and tokens sorted by
   `(lane.value, source/person, target/token, tick)` so canonical output never
   depends on input order.
5. Provide pure adapters, each returning tuples and each documented with the
   accepted source row:
   - `edges_from_communication(rows: Sequence[object]) -> tuple[MacroSocietyEdge, ...]`
     reading `speaker_id`/`listener_id` (fallback `source_person_id`/`target_person_id`)
     and `tick` (default `0`); skip rows whose action kind is not
     `talk`/`ask`/`tell`.
   - `edges_from_interaction(rows)`: reads applied action rows with
     `actor_id`/`target_id` and `tick`; weight `1.0`.
   - `edges_from_journeys(rows)`: reads `SocietyJourneyRow`-shaped rows with
     `person_id`, `origin_region_id`, `destination_region_id`, `tick`; emits one
     edge per ordered person pair that shares origin and destination in the same
     tick, weight `1.0`.
   - `edges_from_exchanges(rows)`: reads `CommitmentItemMove`-shaped rows with
     `from_owner_id`/`to_owner_id` (fallback `source_owner_id`/`target_owner_id`)
     and `tick`; weight `1.0`. Rows missing both owners are skipped, not failed.
   - `tokens_from_institutions(rows)`: `(owner_id, local_pattern_id)` →
     token lane `institution`, token `local_pattern_id`.
   - `tokens_from_culture(rows)`: `carriers` mapping `trait_id -> owner ids` →
     token lane `culture`, token `trait_id`.
   - `tokens_from_territory(rows)`: `(owner_id, target_entity_id)` where
     `target_kind` is `location` or `region` → token lane `territory`.
   - `tokens_from_self_identification(rows)`: `GroupMembership`-shaped
     `(owner_id, group_id)` → token lane `self_identification`, token `group_id`.
   - `tokens_from_collective_decisions(rows)`: `(owner_id, proposal_ref)` →
     token lane `collective_decision`.
   - `tokens_from_residence(rows)`: `(person_id, region_id)` → token lane
     `territory` with a `region:` prefix on the token value.
6. Each adapter accepts `Sequence[object]` and reads attributes by name, matching
   the existing `_person_of` normalization style; a required field that is
   missing or not a stable id raises `macro_society_invalid_evidence_row` with
   the lane in the log line only.
7. Export the adapters and dataclasses from `src/analysis/__init__.py`.

### Required Interfaces and Contracts

- Adapters are total over their documented row shape and never mutate inputs.
- Output ordering is deterministic and independent of input ordering.
- Tokens and edges carry identifiers and weights only — no utterance text,
  labels, narratives, memories, or embeddings.
- A window with no edges and no tokens is valid and produces empty output.

### Error Handling and Logging

- `MacroSocietyError` subclasses are not introduced here; reuse the contract
  error with the codes above.
- `_LOG.debug("macro_society_evidence lane=%s rows=%s edges=%s tokens=%s", ...)`
  logs counts only, never ids.
- Missing optional lanes are normal and produce empty tuples, never a failure.

### Tests

`tests/unit/test_macro_society_evidence.py`:
- Each adapter maps a representative row to the expected lane, endpoints, and
  token, using object stand-ins shaped like the real row classes.
- Communication adapter ignores non-speech action kinds.
- Journey adapter emits no edge for a single traveller and an edge for a shared
  origin/destination pair.
- Self-edges, unknown lanes, unknown persons, non-finite weights, and oversized
  windows raise the documented codes.
- Permuting input rows produces byte-identical canonical tuples.
- Adapters reject rows carrying extra payload attributes without reading them
  (assert the output contains no string from a `utterance` attribute).

### Acceptance Criteria

- Nine lanes are reachable from existing detached sources with no new event,
  command, or ledger.
- A person may hold multiple tokens in one lane and multiple lanes.
- No adapter imports `simulation.engine`, `world._*`, `persistence`, or `api`.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_macro_society_evidence.py -q`
- `uv run --frozen --python 3.12.14 mypy src/analysis/macro_society_evidence.py`

## Task 4: Detect per-lane clusters and compose cross-lane candidates

### Intent

Detection must be deterministic, overlap-capable, and honest about missing
evidence. The output is a candidate, never a partition: an agent can belong to
two candidates when different evidence lanes disagree, and a candidate without
self-identification is still a candidate.

### Implementation Steps

1. Create `src/analysis/macro_society_detection.py` importing the contract,
   evidence types, `networkx`, `analysis.network_metrics`, and
   `analysis.numerical`.
2. Define `@dataclass(frozen=True, slots=True) class MacroSocietyLaneCluster`
   with `lane`, `token_id: str | None`, `member_ids: tuple[str, ...]`.
3. Define `@dataclass(frozen=True, slots=True) class MacroSocietyLaneSupport`
   with `lane`, `member_count`, `cluster_count`.
4. Define `@dataclass(frozen=True, slots=True) class MacroSocietyCandidate` with
   `candidate_key: str`, `member_ids`, `lane_support: tuple[MacroSocietyLaneSupport, ...]`,
   `status: MacroSocietyStatus`, `membership: tuple[tuple[str, MacroSocietyMembershipStatus], ...]`,
   `coverage: MacroSocietyCoverage`, `tick_start`, `tick_end`.
   `candidate_key` is a deterministic content key used only for matching:
   `sha256` over sorted `(lane, token_id | "-", member_ids)` tuples, prefixed
   `msoc-candidate-`, never exposed as a society identity.
5. Define `@dataclass(frozen=True, slots=True) class MacroSocietyWindowResult`
   with `window_index`, `tick_start`, `tick_end`, `candidates`, `overlap_person_ids`,
   `fragment_person_ids`, `known_person_ids`, `coverage`, `lane_presence`.
6. Implement `detect_macro_society_candidates(window: MacroSocietyWindowEvidence) -> MacroSocietyWindowResult`:
   1. For each token lane, group persons by `token_id`; each group with
      `len(group) >= MIN_LANE_CLUSTER_MEMBERS` becomes a lane cluster.
   2. For each edge lane, build an undirected weighted `networkx.Graph` over
      sorted nodes by summing edge weights; run
      `greedy_modularity_communities` (the pinned `SUPPORTED_COMMUNITY_ALGORITHM`);
      canonicalize labels; keep communities with
      `len >= MIN_LANE_CLUSTER_MEMBERS`.
   3. Cross-lane composition: union-find over lane clusters. Union two clusters
      only when their lanes differ and
      `jaccard(members) >= LANE_AGREEMENT_JACCARD`. Iterate pairs in sorted
      `(lane, token_id, candidate member hash)` order so the result is
      order-independent.
   4. Each union component becomes a candidate. Members = sorted union of its
      clusters. `lane_support` = per lane, count of members and contributing
      clusters. Drop components with fewer than `MIN_CANDIDATE_MEMBERS`
      members; their persons join `fragment_person_ids`.
   5. `coverage` = `MacroSocietyCoverage(observed=covered members,
      expected=len(person_ids))`.
   6. Status:
      - `fragmented` if fewer than two lanes contributed or
        `coverage.ratio is not None and coverage.ratio < FRAGMENT_COVERAGE_MIN`.
      - else `contested` if the candidate has at least `CONTESTED_MIN_MEMBERS`
        members whose self-identification cluster was assigned to a different
        candidate (see step 7).
      - else `supported`.
   7. Membership per member: `partial` when the member appears in fewer than half
      of the candidate's contributing lanes, `contested` when the member's own
      self-identification cluster belongs to another candidate, else `supported`.
   8. `overlap_person_ids` = every person in at least two candidates. The
      function never raises for overlap.
   9. Sort candidates by `candidate_key`; sort membership tuples by person id.
7. Determinism: no `hash()`, no set iteration in output, no float comparison
   without `quantize_float`, and identical results under permuted inputs.

### Required Interfaces and Contracts

- Overlap is a supported outcome, not an error; the existing exclusive
  `society_emergence@1` contract is untouched.
- A candidate never carries an objective id, region authority, or world flag.
- `lane_presence` reports which of the nine lanes contributed and which were
  absent, so "no evidence" is never rendered as "no society".
- Runtime complexity is bounded by window caps; oversized windows fail closed
  before clustering.

### Error Handling and Logging

- `macro_society_empty_window` only when `person_ids` is empty.
- `_LOG.debug("macro_society_detection window=%s candidates=%s overlap=%s fragments=%s lanes=%s", ...)`
  with counts only.
- `WARN` is not emitted here; incomplete evidence is represented in
  `lane_presence` and coverage, not in logs.

### Tests

`tests/unit/test_macro_society_detection.py`:
- Two disjoint interaction cliques of four produce two candidates.
- A shared culture token merges two interaction clusters into one candidate.
- A culture token and an institution token with overlapping but non-identical
  members produce one candidate with `partial` membership for the non-shared
  members.
- A person in two distinct token groups yields two candidates and appears in
  `overlap_person_ids`.
- A single-lane candidate below `FRAGMENT_COVERAGE_MIN` is `fragmented`.
- A candidate whose member's self-identification cluster lives elsewhere is
  `contested` with that membership marked `contested`.
- Empty lanes produce an empty result with full `lane_presence` false values.
- Permuting `edges` and `tokens` yields identical candidates and keys.
- A window with `MAX_WINDOW_EDGES + 1` edges raises
  `macro_society_window_too_large` before any graph construction.

### Acceptance Criteria

- No global society object, registry, or exclusive partition is produced.
- Candidate keys are deterministic and stable for identical evidence.
- Every status is reachable by a documented fixture.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_macro_society_detection.py -q`
- `uv run --frozen --python 3.12.14 pytest tests/unit/test_society_emergence*.py -q`
  (existing exclusive behavior unchanged)

## Task 5: Project objective, subjective, and analytical layers separately

### Intent

The request requires three distinguishable representations. This task makes that
separation executable: objective population rows never carry an analytical
society id, subjective rows stay owner-local, and only the analytical layer owns
`msoc-` identities.

### Implementation Steps

1. Create `src/analysis/macro_society_layers.py`.
2. Define `@dataclass(frozen=True, slots=True) class MacroSocietyObjectiveRow`
   with `region_id`, `tick`, `population_count`, `cohort_id: str | None`,
   `stage_id: str | None`. It has no person ids, no candidate ids, and no status.
3. Define `@dataclass(frozen=True, slots=True) class MacroSocietySubjectiveRow`
   with `owner_id`, `lane`, `local_token_id`. It carries the owner's own claim
   only; it never carries a candidate id or another owner's claim.
4. Define `@dataclass(frozen=True, slots=True) class MacroSocietyLayerView` with
   `objective_rows`, `subjective_rows`, `candidate_ids`, `windows`.
5. Implement `project_macro_society_layers(*, window_result, objective_rows, subjective_rows) -> MacroSocietyLayerView`:
   - Copy objective rows through the typed constructor; reject any row object
     exposing `macro_society_id` or `candidate_id` attributes with
     `macro_society_objective_identity_leak`.
   - Copy subjective rows only for owners present in `window_result.known_person_ids`;
     unknown owners are dropped, never merged.
   - `candidate_ids` = sorted candidate keys of the window result.
6. Implement `assert_layer_separation(view) -> None` used by tests and by the
   publication builder: objective rows must not contain any string starting with
   `msoc-`, subjective rows must not contain candidate ids, and candidate ids
   must be unique.
7. Document in the module docstring and in `docs/macro-societies.md` (Task 19)
   that objective structure is reused from `analysis.regional_population`, never
   recomputed and never annotated with identity.

### Required Interfaces and Contracts

- Layer leakage is a hard failure, not a warning.
- Objective rows are counts only; they cannot reconstruct membership.
- Subjective rows remain owner-scoped: no cross-owner aggregation happens here.

### Error Handling and Logging

- `macro_society_objective_identity_leak`, `macro_society_subjective_identity_leak`,
  `macro_society_unknown_person` as applicable.
- `_LOG.debug("macro_society_layers objective=%s subjective=%s candidates=%s", ...)`.

### Tests

`tests/unit/test_macro_society_layers.py`:
- A view built from representative regional rows keeps objective counts but no
  ids.
- Injecting a row with `macro_society_id` raises `macro_society_objective_identity_leak`.
- Injecting a subjective row carrying a candidate id raises
  `macro_society_subjective_identity_leak`.
- Owners absent from the window are dropped.
- `assert_layer_separation` passes for valid views and fails for each violation.

### Acceptance Criteria

- The three representations are structurally distinct types.
- No code path copies subjective rows into objective rows or vice versa.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_macro_society_layers.py -q`

## Phase Risks and Mitigations

- Risk: adapters drift toward reading private payloads.
  Mitigation: adapters return ids/weights/tokens only; the "no utterance" test
  fails if any payload attribute is copied.
- Risk: greedy modularity on very dense windows becomes slow.
  Mitigation: caps are enforced before graph construction; the benchmark lane in
  Task 18 measures the documented cap, not an open-ended size.
- Risk: overlap handling is mistaken for a bug and "fixed" into exclusivity.
  Mitigation: explicit tests plus a non-goal in the registry and docs.

## Phase Completion Checklist

- Every Task 3-5 acceptance criterion is satisfied.
- Nine lanes are reachable and absence is represented, not zero-coerced.
- Overlap, fragmentation, and contention each have a passing fixture.
- `index.md` task checkboxes are updated immediately after verified completion.
