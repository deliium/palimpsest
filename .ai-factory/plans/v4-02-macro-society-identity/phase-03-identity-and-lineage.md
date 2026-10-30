# Phase 3: Stable Identity and Split/Merge Lineage

Plan: [index.md](index.md)
Tasks: 6-7
Depends on: Phase 2 (Tasks 3-5)

## Objective

Give each analytical candidate an identity that survives membership churn and
record how candidates continue, transform, split, merge, emerge, and dissolve
across adjacent observation windows. Identity and lineage are analysis-local:
they never become a `WorldEngine` id, a command target, or a registry entry.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/analysis/macro_society_contract.py` | `derive_macro_society_id`, `MacroSocietyLineageKind`, `LINEAGE_JACCARD`, `ABSORPTION_CONTAINMENT`, `TRANSFORM_JACCARD` | Identity and threshold contract from Task 2. |
| `src/analysis/macro_society_detection.py` | `MacroSocietyCandidate`, `MacroSocietyWindowResult`, `MacroSocietyMembershipStatus` | Inputs to identity assignment. |
| `src/analysis/group_formation_metrics.py` | `_JACCARD = 0.5` (53), `compute_group_persistence` (127), `_lineage_ticks` (609) | Existing adjacent-window Jaccard split/merge convention. |
| `src/analysis/institution_lineage.py` | `_MIN_JACCARD = 0.50` (39), `InstitutionLineageEdgeKind` (46-50), `compute_institution_lineage` (241), `_validate_acyclic` | Lineage edge kinds and acyclicity pattern to mirror. |
| `src/analysis/models.py` | `MetricCoverage` (518) | Coverage semantics already used across analysis. |
| `src/world/identifiers.py` | `require_stable_id`, `require_exact_nonneg_int` | Validation primitives. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/analysis/macro_society_identity.py` | create | Window-to-window matching, ID minting, candidate records. |
| `src/analysis/macro_society_lineage.py` | create | Lineage edges, validation, aggregate analysis object. |
| `src/analysis/__init__.py` | modify | Export new names. |
| `tests/unit/test_macro_society_identity.py` | create | Stability and minting proofs. |
| `tests/unit/test_macro_society_lineage.py` | create | Split/merge/dissolve/emerge proofs. |

## Task 6: Assign stable analytical IDs across windows

### Intent

A macro-society must keep its identity while people arrive and leave, and must
get a new identity when it is genuinely new. Content-derived creation
fingerprints plus overlap matching give both properties without any mutable
counter.

### Implementation Steps

1. Create `src/analysis/macro_society_identity.py`.
2. Define `@dataclass(frozen=True, slots=True) class MacroSocietyRecord` with
   `macro_society_id`, `creation_tick`, `first_tick`, `last_tick`,
   `status: MacroSocietyStatus`, `member_ids: tuple[str, ...]`,
   `lane_signature: tuple[str, ...]`, `window_indexes: tuple[int, ...]`.
   `member_ids` is bounded by `MAX_CANDIDATE_MEMBERS` and sorted.
3. Define `@dataclass(frozen=True, slots=True) class MacroSocietyIdentityAssignment` with `records: tuple[MacroSocietyRecord, ...]`, `window_assignments: tuple[tuple[int, tuple[tuple[str, str], ...]], ...]` (window index → sorted `(candidate_key, macro_society_id)` pairs), `coverage: MacroSocietyCoverage`.
4. Implement `assign_macro_society_identities(windows: Sequence[MacroSocietyWindowResult], *, policy_version: str = MACRO_SOCIETY_POLICY_VERSION) -> MacroSocietyIdentityAssignment`:
   1. Reject more than `MAX_EVIDENCE_WINDOWS` windows
      (`macro_society_too_many_windows`); reject non-increasing window indexes.
   2. Window 0: mint one id per candidate with
      `derive_macro_society_id(creation_tick=tick_start, founding_member_ids=members, lane_signature=contributing lanes)`.
   3. For window k ≥ 1: score every previous-window candidate against every
      current candidate with `jaccard = |P∩C| / |P∪C|` (quantized). Build a
      sorted list of `(-jaccard, previous_id, current_key)` and greedily accept
      pairs with `jaccard >= LINEAGE_JACCARD` where both endpoints are unused.
   4. Map accepted pairs:
      - one previous ↔ one current → the current candidate inherits the
        previous id. Its `status` comes from detection; `creation_tick` is
        inherited.
      - one previous ↔ many current → the previous id is retired at this
        window; every current child mints a new id. (Split identity rule.)
      - many previous ↔ one current → the current candidate mints a new id.
        (Merge identity rule: a merged society is a new analytical identity.)
      - one previous unmatched and not absorbed → the record ends
        (`last_tick = previous.tick_end`), no new assignment.
      - one previous unmatched but `containment >= ABSORPTION_CONTAINMENT` in
        exactly one current candidate → treat as the one-to-one case and inherit
        the id, with `policy_note` recorded on the lineage edge as
        `absorption`.
      - one current unmatched → mint a new id.
   5. Minting always uses the current candidate's own creation evidence; a minted
      id can never collide with an existing one (assert uniqueness and raise
      `macro_society_id_collision` if a 16-hex prefix collides).
   6. Append each window's assignment; update each record's `last_tick`,
      `member_ids`, `status`, and `window_indexes`.
   7. Sort records by `(creation_tick, macro_society_id)`.
5. Implement `record_for(assignment, macro_society_id)` and
   `record_at(assignment, window_index, candidate_key)` lookup helpers that raise
   `macro_society_unknown_society` for unknown ids.
6. Determinism: no `hash()`, no dict-order leakage, quantized floats.

### Required Interfaces and Contracts

- One `macro_society_id` is minted once and only at a candidate's first
  observation.
- Membership churn below `LINEAGE_JACCARD` keeps the id; churn above it produces
  a new identity plus a lineage edge (Task 7).
- Split children and merge results always receive new ids; parent ids are never
  reused for a different member set.
- Records never carry person content, labels, or free text.

### Error Handling and Logging

- `macro_society_too_many_windows`, `macro_society_nonmonotonic_window`,
  `macro_society_id_collision`, `macro_society_unknown_society`.
- `_LOG.debug("macro_society_identity windows=%s records=%s minted=%s inherited=%s", ...)`.

### Tests

`tests/unit/test_macro_society_identity.py`:
- Two identical windows produce one record with one stable id.
- Small churn (one member replaced of ten) keeps the id.
- Large churn (six of ten replaced, Jaccard < 0.5) mints a new id.
- Three windows with a stable candidate keep exactly one id and three window
  indexes.
- A candidate that disappears and an unrelated candidate that appears get
  distinct ids.
- Permuting candidate order inside each window yields identical assignments.
- A 513-window sequence raises `macro_society_too_many_windows`.
- `creation_tick` equals the first window's `tick_start`, not the current tick.

### Acceptance Criteria

- Identity is stable for stable evidence and new for new evidence.
- No mutable counter, UUID, or wall-clock participates in an id.
- Records are immutable and sorted deterministically.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_macro_society_identity.py -q`
- `PYTHONHASHSEED=0` and `PYTHONHASHSEED=7` runs produce identical ids.

## Task 7: Derive split/merge lineage with acyclicity validation

### Intent

Lineage is the historical explanation of analytical identity, so it must be
complete (every identity change has an edge), monotonic (edges point forward in
time), and unambiguous (split and merge fan-out are exact).

### Implementation Steps

1. Create `src/analysis/macro_society_lineage.py`.
2. Define `@dataclass(frozen=True, slots=True) class MacroSocietyLineageEdge`
   with `from_id: str | None`, `to_id: str | None`, `kind: MacroSocietyLineageKind`,
   `from_tick: int`, `to_tick: int`, `jaccard: float | None`,
   `policy_note: str | None`. Exactly one of `from_id`/`to_id` may be `None` and
   only for `emerged` (`from_id=None`) or `dissolved` (`to_id=None`).
3. Define `@dataclass(frozen=True, slots=True) class MacroSocietyAnalysis` with
   `policy_version`, `windows`, `records`, `edges`, `layer_view`, `coverage`,
   `determinism_digest`. `determinism_digest` is SHA-256 over the canonical JSON
   of windows, records, and edges.
4. Implement `derive_macro_society_lineage(*, assignment, windows) -> tuple[MacroSocietyLineageEdge, ...]`:
   - For each accepted pair from the identity matching, emit `continued` when
     `jaccard >= TRANSFORM_JACCARD`, `transformed` when
     `LINEAGE_JACCARD <= jaccard < TRANSFORM_JACCARD`, or `transformed` with
     `policy_note="absorption"` for the containment path.
   - For one previous ↔ many current, emit one `split` edge per child.
   - For many previous ↔ one current, emit one `merge` edge per parent.
   - For an unmatched previous, emit `dissolved` with `to_id=None`.
   - For an unmatched current, emit `emerged` with `from_id=None`.
5. Implement `validate_macro_society_lineage(edges, records) -> None`:
   - `from_tick < to_tick` (`macro_society_lineage_nonmonotonic_tick`).
   - No duplicate `(from_id, to_id, kind)` (`macro_society_lineage_duplicate_edge`).
   - Every referenced id exists in `records` (`macro_society_unknown_society`).
   - Build a directed graph over ids and reject cycles with
     `macro_society_lineage_cycle` (mirror `analysis.institution_lineage._validate_acyclic`).
   - Enforce exact fan-out: the set of `split` children of one parent must have
     more than one member, and the set of `merge` parents of one child must have
     more than one member
     (`macro_society_lineage_ambiguous_parent`).
   - Bound total edges by `MAX_LINEAGE_EDGES`
     (`macro_society_lineage_too_large`).
6. Implement `build_macro_society_analysis(*, windows, layer_view, assignment) -> MacroSocietyAnalysis`
   that derives edges, validates them, and computes `determinism_digest`.
7. Document that `dissolved` is not death and `emerged` is not birth: they are
   analytical visibility changes, never world facts.

### Required Interfaces and Contracts

- Every lineage edge is analysis-local; `from_id`/`to_id` are never command
  targets or event references.
- History is append-only within a run: a later window never rewrites an earlier
  edge.
- `determinism_digest` changes when any window, record, or edge changes.

### Error Handling and Logging

- The five lineage codes above, plus `macro_society_lineage_too_large`.
- `_LOG.debug("macro_society_lineage edges=%s continued=%s split=%s merge=%s dissolved=%s emerged=%s", ...)`.

### Tests

`tests/unit/test_macro_society_lineage.py`:
- One stable candidate across three windows yields two `continued` edges and no
  split/merge.
- A candidate splitting into two children yields two `split` edges and two new
  child ids.
- Two candidates merging yield two `merge` edges and one new id.
- A disappearing candidate yields exactly one `dissolved` edge with `to_id=None`.
- A new candidate yields exactly one `emerged` edge with `from_id=None`.
- A hand-built cycle raises `macro_society_lineage_cycle`.
- A hand-built backward edge raises `macro_society_lineage_nonmonotonic_tick`.
- A single-child `split` set raises `macro_society_lineage_ambiguous_parent`.
- `determinism_digest` is 64 lowercase hex characters and changes when one
  member changes.

### Acceptance Criteria

- Every identity transition in Task 6 has a matching edge and no extra edge.
- Lineage graphs are acyclic and forward-only.
- Split and merge are distinguishable from continuation and dissolution.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_macro_society_lineage.py -q`
- `uv run --frozen --python 3.12.14 pytest tests/unit/test_institution_lineage.py -q`
  (existing lineage semantics unchanged)

## Phase Risks and Mitigations

- Risk: greedy matching order causes non-deterministic splits on near-ties.
  Mitigation: the sort key includes previous id and candidate key, and tests
  permute inputs.
- Risk: a merged society silently inherits a parent id, hiding the merge.
  Mitigation: merges always mint a new id, enforced by a test.
- Risk: lineage is mistaken for objective history.
  Mitigation: module docstring, registry non-goals, and Task 17 AST checks
  forbid world imports and command types.

## Phase Completion Checklist

- Every Task 6-7 acceptance criterion is satisfied.
- IDs are minted once, never reused, and recorded with their creation tick.
- Lineage is acyclic, monotone, and complete for the fixtures.
- `index.md` task checkboxes are updated immediately after verified completion.
