# Phase 1: Context and Closed Contract

Plan: [index.md](index.md)
Tasks: 1-2
Depends on: none

## Objective

Declare the fourteenth V4 context — `macro_society_identity`, detached analysis,
no capability flag — and freeze the closed macro-society analytical vocabulary
(lanes, statuses, lineage kinds, policy constants, stable-ID derivation) in one
owned module. After this phase the repository has a single machine-readable
statement of what a macro-society candidate may and may not be, and nothing can
detect, store, or serve one yet.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/simulation/v4_architecture.py` | `V4_CONTEXT_MAP_VERSION` (38), `_REQUIRED_CONTEXT_COUNT` (56), `V4ContextId` (60-75), `V4ContextSpec` (87-99), `V4_CONTEXTS` (102), `V4_ANALYSIS_ONLY_CONTEXTS` (296), `validate_v4_contexts` (337-386) | Registry that must gain a fourteenth, analysis-only entry. |
| `src/simulation/v4_architecture.py` | `V4_ANALYSIS_CAPTURE_SEAM` (39), analysis branch of `validate_v4_contexts` (358-367) | Analysis contexts must own only `analysis`, carry no flag, and use the `analysis_capture` seam. |
| `src/simulation/versioning.py` | imports `V4_ANALYSIS_ONLY_CONTEXTS` (16), reservation validation (134) | Analysis-only contexts must never reserve a write pair; four reservations must stay exactly four. |
| `tests/architecture/test_v4_context_registry.py` | map-version pin (99), `len(V4_CONTEXTS) == 13` (100), analysis-only test (107-116), doc-heading count (165) | Every one of these literals must move deliberately. |
| `tests/architecture/test_v4_architecture_invariants.py` | `V4_ANALYSIS_ONLY_CONTEXTS == frozenset({V4ContextId.SOCIETAL_RESILIENCE})` (159) | Second analysis-only context must be admitted explicitly. |
| `docs/v4-architecture.md` | context table row (69), `### societal_resilience` (159) | Documentation parity is test-enforced. |
| `src/analysis/society_emergence.py` | `derive_community_id` (66-72), `SocietyEmergenceError` (57-63), `_LOG` (54) | Existing content-derived ID and fail-closed error-code style to mirror. |
| `src/world/identifiers.py` | `require_stable_id`, `require_exact_nonneg_int` | Validation primitives used by every analysis row type. |
| `src/analysis/numerical.py` | `quantize_float`, `sorted_graph_nodes`, `SUPPORTED_COMMUNITY_ALGORITHM` | Deterministic numeric and graph helpers to reuse. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/simulation/v4_architecture.py` | modify | Add `MACRO_SOCIETY_IDENTITY`; registry entry; count 14; map version v2; analysis-only set. |
| `src/simulation/__init__.py` | modify | No new names required if the enum entry is additive; verify the module is re-exported. |
| `src/analysis/macro_society_contract.py` | create | Closed vocabulary, policy constants, error type, stable-ID derivation. |
| `src/analysis/__init__.py` | modify | Export contract names and `__all__` entries. |
| `tests/architecture/test_v4_context_registry.py` | modify | 14 contexts, map v2, two analysis-only contexts, doc-heading count. |
| `tests/architecture/test_v4_architecture_invariants.py` | modify | Analysis-only set assertion. |
| `tests/unit/test_macro_society_contract.py` | create | Contract and ID-derivation proofs. |
| `docs/v4-architecture.md` | modify | Table row, `### macro_society_identity` section, context count. |

## Task 1: Extend the V4 context registry with the macro-society context

### Intent

Make the analysis-only nature of this feature a machine-checked declaration
before any code exists. The registry is the only place allowed to state that
macro-societies are detached research constructs; extending it here prevents a
later implementer from inventing a capability flag, a world seam, or a global
registry.

### Implementation Steps

1. In `src/simulation/v4_architecture.py` append to `V4ContextId`:
   `MACRO_SOCIETY_IDENTITY = "macro_society_identity"`.
2. Append one `V4ContextSpec` to `V4_CONTEXTS` after `SOCIETAL_RESILIENCE` with
   exactly these values:
   - `context_id=V4ContextId.MACRO_SOCIETY_IDENTITY`
   - `capability_flag=None`
   - `authority=V4Authority.DETACHED_ANALYSIS`
   - `owner_packages=("analysis",)`
   - `existing_mechanism="candidate-community analysis, cultural/institutional evidence joins, group persistence"`
   - `required_config_seam=V4_ANALYSIS_CAPTURE_SEAM`
   - `uses_existing_events=True`
   - `prerequisite_contexts=()`
   - `non_goals=("no objective nation, state, polity, or civilization entity", "no global society registry or WorldEngine identity", "no exclusive partition of persons or forced single membership", "no feedback into cognition, memory, prompts, admission, or stop selectors")`
3. Add `V4ContextId.MACRO_SOCIETY_IDENTITY` to `V4_ANALYSIS_ONLY_CONTEXTS` and
   raise `_REQUIRED_CONTEXT_COUNT` to `14`.
4. Set `V4_CONTEXT_MAP_VERSION = "v4-context-map-v2"`. The registry shape is an
   additive versioned contract; a new context is a new map revision, never a
   silent edit of `v4-context-map-v1`.
5. Do not add a flag, sealed reservation, runner field, or migration. Assert by
   inspection that `V4_WRITE_PAIR_RESERVATIONS` in `src/simulation/versioning.py`
   still contains exactly four entries.
6. Update `docs/v4-architecture.md`: add the row
   ``| `macro_society_identity` | — (analysis-only) | detached-analysis | `analysis` | candidate-community analysis, cultural/institutional evidence joins, group persistence | reuse | deferred to V4-02 implementation |``
   to the context table and add a `### macro_society_identity` section after
   `### societal_resilience` describing authority, non-goals, and the fact that
   every identifier is analysis-local.
7. Leave `.ai-factory/ARCHITECTURE.md` untouched in this task. Its V4-02 seam
   section, the 14-context statement, and the 140-family count belong to the
   documentation checkpoint (Task 19) so registry code and architecture prose are
   not edited twice.

### Required Interfaces and Contracts

- `V4ContextId` gains exactly one member; `V4_CONTEXTS` gains exactly one entry.
- `validate_v4_contexts()` passes with the default registry and still raises
  `v4_context_count` for a 13-element copy.
- `v4_context_for_flag("macro_society_identity")` raises
  `ValueError("v4_context_unknown_flag")`.
- `v4_owner_packages()` still returns the same package set (no new package).
- Registry order is stable and appended last, so every existing test that zips
  flags with contexts keeps its order.

### Error Handling and Logging

- No new runtime logging. Registry validation keeps its existing stable codes
  (`v4_context_*`).
- Do not log context payloads.

### Tests

- `tests/architecture/test_v4_context_registry.py`:
  - `V4_CONTEXT_MAP_VERSION == "v4-context-map-v2"`.
  - `len(V4_CONTEXTS) == 14`.
  - `test_only_resilience_is_analysis_only_and_carries_no_flag` becomes
    `test_analysis_only_contexts_carry_no_flag` and asserts
    `V4_ANALYSIS_ONLY_CONTEXTS == frozenset({V4ContextId.SOCIETAL_RESILIENCE, V4ContextId.MACRO_SOCIETY_IDENTITY})`.
  - doc-heading count is `14`.
- `tests/architecture/test_v4_architecture_invariants.py`: update the
  analysis-only frozenset literal and the reserved-pair count if it is pinned.
- New assertions in the registry test: the macro-society context has
  `capability_flag is None`, `owner_packages == ("analysis",)`,
  `required_config_seam == "analysis_capture"`, non-empty non-goals, and an
  empty prerequisite tuple.

### Acceptance Criteria

- Registry validation passes with 14 contexts and fails closed for 13 or 15.
- No capability flag name, runner schema, reservation, or migration changed.
- Documentation lists the context and the map revision.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_v4_context_registry.py tests/architecture/test_v4_architecture_invariants.py tests/unit/test_v4_versioning_reservations.py -q`
- Expected: all pass; reservation count still four.

## Task 2: Freeze the closed macro-society analytical contract

### Intent

One module owns the vocabulary so detection, lineage, metrics, artifact, and API
cannot drift apart. IDs are derived here and nowhere else, which is what keeps
"stable analytical ID" a property of evidence rather than a mutable counter.

### Implementation Steps

1. Create `src/analysis/macro_society_contract.py` with a module docstring that
   states: read-only; never imports persistence, API, experiments, observer, or
   world authority; a macro-society is an analysis-output label only.
2. Constants (`Final`):
   - `MACRO_SOCIETY_POLICY_VERSION = "macro-society-identity.v1"`
   - `MACRO_SOCIETY_ID_NAMESPACE = "macro-society-identity-v1"`
   - `MACRO_SOCIETY_ID_PREFIX = "msoc-"`
   - `MACRO_SOCIETY_ID_HEX_CHARS = 16`
   - `MIN_CANDIDATE_MEMBERS = 4`
   - `MIN_LANE_CLUSTER_MEMBERS = 4`
   - `LANE_AGREEMENT_JACCARD = 0.5`
   - `LINEAGE_JACCARD = 0.5`
   - `TRANSFORM_JACCARD = 0.75`
   - `ABSORPTION_CONTAINMENT = 0.5`
   - `FRAGMENT_COVERAGE_MIN = 0.4`
   - `CONTESTED_MIN_MEMBERS = 2`
   - `MAX_EVIDENCE_WINDOWS = 512`
   - `MAX_WINDOW_PERSONS = 20000`
   - `MAX_WINDOW_EDGES = 50000`
   - `MAX_CANDIDATE_MEMBERS = 512`
   - `MAX_WINDOW_CANDIDATES = 2048`
   - `MAX_LINEAGE_EDGES = 16384`
3. Enums (`StrEnum`):
   - `MacroSocietyLane`: `interaction`, `communication`, `migration`, `exchange`,
     `institution`, `culture`, `territory`, `self_identification`,
     `collective_decision`.
   - `MacroSocietyLaneKind`: `edge`, `token` — with
     `EDGE_LANES = frozenset({interaction, communication, migration, exchange})`
     and `TOKEN_LANES` as the complement.
   - `MacroSocietyStatus`: `supported`, `fragmented`, `contested`.
   - `MacroSocietyMembershipStatus`: `supported`, `partial`, `contested`.
   - `MacroSocietyLayer`: `objective_population`, `subjective_identity`,
     `analytical_candidate`.
   - `MacroSocietyLineageKind`: `continued`, `transformed`, `split`, `merge`,
     `dissolved`, `emerged`.
4. `class MacroSocietyError(ValueError)` with `reason_code: str`, validated by
   `require_stable_id`, and a module `_LOG.debug("macro_society_invalid reason_code=%s", ...)`.
5. `@dataclass(frozen=True, slots=True) class MacroSocietyCoverage` with
   `observed: int`, `expected: int`, `ratio: float | None`; reject negative or
   `observed > expected` counts; `ratio` = quantized `observed/expected` or
   `None` when `expected == 0`.
6. `derive_macro_society_id(*, creation_tick: int, founding_member_ids: Iterable[str], lane_signature: Iterable[str]) -> str`:
   - Normalize members to a sorted, de-duplicated tuple; reject an empty set
     (`macro_society_empty_member_set`) and duplicates
     (`macro_society_duplicate_member`).
   - Normalize lanes to sorted enum values; reject unknown or empty
     (`macro_society_unknown_lane`).
   - Build canonical JSON `{"namespace": MACRO_SOCIETY_ID_NAMESPACE,
     "creation_tick": tick, "founding_member_ids": [...], "lane_signature": [...]}`
     with `sort_keys=True, separators=(",", ":")`, encode UTF-8, SHA-256.
   - Return `f"{MACRO_SOCIETY_ID_PREFIX}{digest[:MACRO_SOCIETY_ID_HEX_CHARS]}"`.
   - Never use `hash()`, `uuid`, wall-clock, or process state.
7. `require_macro_society_id(value: str) -> str`: exact `msoc-` + 16 lowercase
   hex characters, else `macro_society_invalid_id`.
8. `validate_member_ids(name: str, raw: object) -> tuple[str, ...]`: reject
   `str`/`bytes` inputs (`macro_society_content_payload_rejected`), reject
   duplicates, sort, require at least one id.
9. Export every public name plus `__all__`; re-export from
   `src/analysis/__init__.py` following the existing society import block.

### Required Interfaces and Contracts

- `derive_macro_society_id` is pure and total over validated inputs; equal
  founding evidence always yields the same id on any platform.
- IDs are minted only at first observation of a candidate (`creation_tick`), so
  later membership churn cannot rename an existing analytical society.
- No member content, label, name, or free text enters the id input.
- The module imports only the standard library, `world.identifiers`, and
  `analysis.numerical`.

### Error Handling and Logging

- Every rejection raises `MacroSocietyError` with a stable `reason_code`; the
  exception message is the code only.
- `_LOG.debug` records the code and nothing else. No member ids, no counts that
  could identify a person set.

### Tests

`tests/unit/test_macro_society_contract.py`:
- ID is `msoc-` + 16 hex chars and stable across `PYTHONHASHSEED` values.
- Member-order permutation and lane-order permutation yield the same id.
- Different `creation_tick`, one different member, or one different lane yields
  a different id.
- Empty members, duplicate members, unknown lane, bad tick, and content payload
  raise the documented codes.
- `require_macro_society_id` rejects wrong prefix, wrong length, and uppercase
  hex.
- `MacroSocietyCoverage` rejects `observed > expected`, negative values, and
  yields `ratio is None` for `expected == 0`.
- AST-style check: the module source does not contain `hash(`.

### Acceptance Criteria

- Exactly one ID derivation exists in the repository and it is this function.
- All reason codes are stable identifiers accepted by `require_stable_id`.
- Contract imports cannot create a cycle with `analysis` public facades.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_macro_society_contract.py -q`
- `PYTHONHASHSEED=1` and `PYTHONHASHSEED=2` produce identical digests for the
  same inputs (run the ID test twice with different seeds).
- `uv run --frozen --python 3.12.14 ruff check src/analysis/macro_society_contract.py`
- `uv run --frozen --python 3.12.14 mypy src/analysis/macro_society_contract.py`

## Phase Risks and Mitigations

- Risk: a registry bump breaks unrelated V4-01 assertions that pin "13".
  Mitigation: grep for `13`, `v4-context-map-v1`, and
  `SOCIETAL_RESILIENCE}` under `tests/architecture/` and update every literal in
  Task 1; run both architecture test modules.
- Risk: the map version bump is mistaken for a protocol bump.
  Mitigation: the version is documented as a registry revision; observer
  protocol and `/version` payload are untouched.
- Risk: the contract module grows behavior.
  Mitigation: Tasks 3-7 add separate modules; this file stays declarative.

## Phase Completion Checklist

- Every Task 1-2 acceptance criterion is satisfied.
- Registry validation passes at 14 contexts with four reservations unchanged.
- No new capability flag, command, event, route, or migration exists.
- `index.md` task checkboxes are updated immediately after verified completion.
