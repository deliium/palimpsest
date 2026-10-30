# Phase 3: Wire and Persistence Evolution

Plan: [index.md](index.md)
Tasks: 7-8
Depends on: Phase 1 (Tasks 1-3), Phase 2 (Tasks 4-6)

## Objective

Reserve the future wire and persistence evolution without implementing it. The
repository gains one declarative write-pair reservation table and one ordered
migration sequence, both validated against the live V3 pins. No event schema,
codec, or Alembic revision is added.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/world/events.py` | `EVENT_SCHEMA_REPLAY_V22` (89), `SUPPORTED_EVENT_SCHEMA_VERSIONS` (90) | Current maximum event schema is 22. |
| `src/simulation/persistence.py` | `ACCEPTED_EVENT_SCHEMA_VERSIONS` (112), `ACCEPTED_PERSISTENCE_CODEC_VERSIONS` (139) | Current accepted maximum is event 22 / codec `v20`. |
| `src/simulation/persistence.py` | `checkpoint_schema_for_production` (254) | Feature-to-write-pair selection; V4 must not extend it in V4-01. |
| `src/simulation/compatibility.py` | `ALEMBIC_HEAD_REVISION`, event/codec matrix rows | Single source of the current pinned head. |
| `alembic/versions/0017_memory_embedding_hnsw.py` | `revision = "0017"` | Current head; no `0018` exists. |
| `docs/persistence.md` | head `0017` rule | Migration policy that the sequence must respect. |
| `tests/unit/test_alembic_head_pin.py` | `test_alembic_head_is_0017_with_memory_embedding_hnsw` | Existing head pin. |
| `tests/architecture/test_path_dependence_boundaries.py` | event/codec pins (79-87) | Existing replay/codec pin. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/simulation/versioning.py` | create | Reserved write-pair table and validators. |
| `src/simulation/migration_plan.py` | create | Ordered migration stages and validators. |
| `src/simulation/__init__.py` | modify | Export both modules' public surfaces. |
| `tests/unit/test_v4_versioning_reservations.py` | create | Reservation invariants. |
| `tests/unit/test_v4_migration_plan.py` | create | Migration-order and no-unplanned-migration invariants. |

## Task 7: Reserve future event and codec write pairs

### Intent

Prevent two later V4 plans from claiming the same event schema or codec version,
and make it explicit which contexts must reuse existing events. Reservations are
metadata only; nothing in this task changes encoding, decoding, or runtime
selection.

### Implementation Steps

1. Create `src/simulation/versioning.py` with:
   - `V4_VERSION_RESERVATION_SCHEMA: Final[str] = "v4-write-pair-reservations-v1"`.
   - `@dataclass(frozen=True, slots=True) class WritePairReservation` with
     fields `context_id: V4ContextId`, `event_schema: int`,
     `codec_version: str`, `prerequisite_flags: tuple[str, ...]`,
     `owner_package: str`, `reason: str`.
   - `V4_WRITE_PAIR_RESERVATIONS: Final[tuple[WritePairReservation, ...]]`:
     1. `infrastructure_networks` — event 23, codec `"v21"`, flags
        `("infrastructure_networks", "supply_chains")`, owner `"world"`, reason
        "physical network topology, capacity, and condition need effect-complete
        replay".
     2. `epidemics` — event 24, codec `"v22"`, flags `("epidemics",)`, owner
        `"world"`, reason "host/transmission state changes must replay".
     3. `ecological_feedback` — event 25, codec `"v23"`, flags
        `("ecological_feedback",)`, owner `"world"`, reason "regeneration and
        depletion coupling must replay".
     4. `disasters` — event 26, codec `"v24"`, flags `("disasters",)`, owner
        `"world"`, reason "multi-location hazard onset/effect must replay".
   - `V4_EVENT_REUSING_CONTEXTS: Final[frozenset[V4ContextId]]` with the other
     nine contexts: `organizations`, `formal_rules`, `legal_disputes`,
     `diplomacy`, `organized_conflict`, `supply_chains`, `markets_credit`,
     `science`, `societal_resilience`.
   - `validate_write_pair_reservations() -> None` raising `ValueError` with
     stable codes: `v4_pair_duplicate_event`, `v4_pair_duplicate_codec`,
     `v4_pair_noncontiguous_event`, `v4_pair_noncontiguous_codec`,
     `v4_pair_unknown_context`, `v4_pair_unknown_flag`,
     `v4_pair_analysis_context`, `v4_pair_uncovered_context`,
     `v4_pair_overlap`.
   - `reservation_for_context(context_id: V4ContextId) -> WritePairReservation`.
2. Validation rules:
   - Reserved event schemas are a contiguous ascending run starting at
     `EVENT_SCHEMA_REPLAY_V22 + 1`.
   - Reserved codec versions are a contiguous ascending run starting at
     `"v21"`, parsed as `int(version[1:])`.
   - Every reservation context is a known `V4ContextId`, is not analysis-only,
     has a non-`None` capability flag, and lists `"world"` or `"simulation"` as
     `owner_package`.
   - Every prerequisite flag exists in `V4_CAPABILITY_FLAG_NAMES`.
   - `V4_EVENT_REUSING_CONTEXTS` and reservation contexts are disjoint and
     together cover exactly `set(V4ContextId)`.
3. Do not add `EVENT_SCHEMA_REPLAY_V23`, any codec string, or any branch in
   `checkpoint_schema_for_production`. The module imports the current maximum
   constants only.
4. Export `V4_WRITE_PAIR_RESERVATIONS`, `WritePairReservation`,
   `reservation_for_context`, `validate_write_pair_reservations`, and
   `V4_EVENT_REUSING_CONTEXTS` from `src/simulation/__init__.py`.
5. Create `tests/unit/test_v4_versioning_reservations.py`:
   - `validate_write_pair_reservations()` passes.
   - The first reservation is event 23 / codec `"v21"` and the last is event 26
     / codec `"v24"`.
   - `max(ACCEPTED_EVENT_SCHEMA_VERSIONS) == 22` and
     `"v21" not in ACCEPTED_PERSISTENCE_CODEC_VERSIONS`.
   - `EVENT_SCHEMA_REPLAY_V23` does not exist on `world.events` (assert with
     `hasattr`).
   - Coverage and disjointness hold.
   - A duplicated event, duplicate codec, gap, unknown context, analysis-only
     context, and uncovered context each raise the documented code in a
     deliberately mutated copy (build tuples locally; do not monkeypatch the
     frozen constant).
   - Importing `simulation.versioning` logs nothing and opens no resources.

### Required Interfaces and Contracts

- Reservations are immutable metadata; no runtime path reads them in V4-01.
- `owner_package` values stay inside `{"world", "simulation"}`.
- Reserved numbers are not reserved *semantics*: later plans must still prove
  replay and complete-effect payloads before implementing the pair.
- `validate_write_pair_reservations()` is deterministic and side-effect free.

### Requirement Evidence

- Original Request: "event versioning" and "migration sequence".
- `src/simulation/persistence.py` current maxima and write-pair selection.
- `.ai-factory/ARCHITECTURE.md` versioned extension contract.

### Error Handling and Logging

- Pure validation; failures raise `ValueError` with the documented codes.
- No logging at import; callers may log `v4_write_pair_reservation_count=4` at
  DEBUG.

### Tests

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_v4_versioning_reservations.py -q`

### Acceptance Criteria

- Four reservations validate and cover exactly the four objective contexts that
  need new events.
- The other nine contexts are declared event-reusing.
- Current accepted event/codec maxima are unchanged.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_v4_versioning_reservations.py -q`
- Expected result: all tests pass, 0 failures.

## Task 8: Define the ordered migration sequence

### Intent

Commit the order in which V4 may add persistence, with the evidence trigger that
must be proven first. V4-01 adds no migration; the sequence exists so later plans
cannot introduce migrations out of order or "just in case".

### Implementation Steps

1. Create `src/simulation/migration_plan.py` with:
   - `V4_MIGRATION_PLAN_SCHEMA: Final[str] = "v4-migration-sequence-v1"`.
   - `@dataclass(frozen=True, slots=True) class MigrationStage` with fields
     `order: int`, `stage_id: str`, `requires_migration: bool`,
     `trigger: str`, `prerequisite_flags: tuple[str, ...]`,
     `owner_package: str`, `authority_impact: str`.
   - `V4_MIGRATION_SEQUENCE`:
     1. `v4-m01-capability-scaffolding` — order 1, no migration, trigger
        "V4-01 flags and version acceptance only", no flags, owner
        `"simulation"`, impact `"none"`.
     2. `v4-m02-objective-network-state` — order 2, migration required, trigger
        "proven indexed inspection need for network topology, capacity, or
        condition across runs", flags `("infrastructure_networks",
        "supply_chains")`, owner `"persistence"`, impact "additive objective
        tables/indexes only".
     3. `v4-m03-epidemic-host-state` — order 3, migration required, trigger
        "proven indexed need for host/transmission history", flags
        `("epidemics",)`, owner `"persistence"`, impact "additive objective
        tables/indexes only".
     4. `v4-m04-ecological-state` — order 4, migration required, trigger
        "proven indexed need for regeneration/depletion history", flags
        `("ecological_feedback",)`, owner `"persistence"`, impact "additive
        objective tables/indexes only".
     5. `v4-m05-disaster-state` — order 5, migration required, trigger "proven
        indexed need for multi-location hazard history", flags `("disasters",)`,
        owner `"persistence"`, impact "additive objective tables/indexes only".
     6. `v4-m06-resilience-read-model` — order 6, migration required, trigger
        "detached resilience queries exceed bounded in-memory aggregation",
        flags `()`, owner `"persistence"`, impact "read-model indexes only; no
        cognition or world authority". `societal_resilience` is analysis-only
        and has no runner capability flag, so this stage is gated by a proven
        read-model need rather than a flag.
   - `validate_migration_sequence(current_head: str = ALEMBIC_HEAD_REVISION) -> None`
     raising `ValueError` with stable codes:
     `v4_migration_order`, `v4_migration_duplicate_stage`,
     `v4_migration_stage_prefix`, `v4_migration_unknown_flag`,
     `v4_migration_gap_after_migration`, `v4_migration_head_mismatch`.
   - `next_revision(current_head: str = ALEMBIC_HEAD_REVISION) -> str` returning
     the zero-padded four-digit successor (currently `"0018"`).
   - `unapplied_stages(current_head: str = ALEMBIC_HEAD_REVISION) -> tuple[MigrationStage, ...]`
     returning every `requires_migration` stage while the head is the current
     value.
   - `future_migration_files(directory: Path, current_head: str = ALEMBIC_HEAD_REVISION) -> tuple[Path, ...]`
     returning `NNNN_*.py` files whose numeric prefix is greater than the head.
2. Validation rules:
   - Order is contiguous from 1 and stage ids are unique and start with `v4-m`.
   - Once a stage requires migration, no later stage may set it to `False`.
   - Every prerequisite flag exists in `V4_CAPABILITY_FLAG_NAMES`.
   - `current_head` must equal `ALEMBIC_HEAD_REVISION`; otherwise raise the
     head-mismatch code (this forces a later plan to update the constant and the
     plan intentionally).
3. `migration_plan.py` must not import SQLAlchemy, Alembic, `persistence`, or
   `infrastructure`; it is pure metadata.
4. Export the module surface from `src/simulation/__init__.py`.
5. Create `tests/unit/test_v4_migration_plan.py`:
   - `validate_migration_sequence()` passes; `next_revision() == "0018"`.
   - `future_migration_files(ROOT / "alembic" / "versions")` is empty.
   - `unapplied_stages()` returns stages 2-6 in order and excludes stage 1.
   - Stage 6 has no prerequisite flags (analysis-only resilience has no runner
     flag), while stages 2-5 each name only known `V4_CAPABILITY_FLAG_NAMES`.
   - A reordered copy, duplicate stage id, unknown flag, and post-migration
     `False` stage each raise the documented code.
   - A mismatched head raises `v4_migration_head_mismatch`.
   - A temporary directory containing `0018_example.py` is reported by
     `future_migration_files`, and `0017_*.py` is not.
   - AST check: the module imports no forbidden stack.

### Required Interfaces and Contracts

- The sequence is ordered, immutable, and describes intent only.
- No Alembic revision is created in V4-01; head stays `0017`.
- `authority_impact` values must state whether authority changes; only
  `"none"` and additive/read-model impacts are allowed in V4-01.

### Requirement Evidence

- Original Request: "migration sequence".
- `docs/persistence.md`: migrations are added only for a proven persistence or
  indexed-inspection need, not automatically per feature.
- `tests/unit/test_alembic_head_pin.py` head pin.

### Error Handling and Logging

- Pure validation; `ValueError` with stable codes.
- No logging; later execution plans log applied revisions at INFO.

### Tests

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_v4_migration_plan.py tests/unit/test_alembic_head_pin.py -q`

### Acceptance Criteria

- Six ordered stages validate; none is applied.
- Head stays `0017`; no future migration file exists.
- The first future stage maps to revision `0018`.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_v4_migration_plan.py -q`
- Expected result: all tests pass, 0 failures.
- `uv run --frozen --python 3.12.14 pytest tests/unit/test_alembic_head_pin.py -q`
  still passes.

## Phase Risks and Mitigations

- Risk: reservations become an implicit commitment to specific event shapes.
  Mitigation: `reason` and the doc state that numbers are reserved, not
  semantics; later plans must still prove replay and payload completeness.
- Risk: migration stages are mistaken for approved migrations.
  Mitigation: stage 1 is explicitly non-migrating, triggers are required
  evidence, and the no-unplanned-file test fails if `0018` appears early.
- Risk: context coverage drifts when V4-02 adds a context.
  Mitigation: reservation coverage is validated against `V4_CONTEXTS`; adding a
  context without updating the table fails the test.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
