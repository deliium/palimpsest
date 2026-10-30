# Phase 1: Baseline and Context Map

Plan: [index.md](index.md)
Tasks: 1-3
Depends on: none

## Objective

Make the completed V3 surface trustworthy as a V4 baseline, and commit the V4
bounded-context map as both a human decision record and a machine-checkable
registry. No V4 behavior is introduced in this phase.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/simulation/journal.py` | `_decode_world_event` (line 2521), version bound at line 2549, `EVENT_SCHEMA_REPLAY_V21` import (line 69) | The journal codec rejects V22 events even though `checkpoint_schema_for_production()` writes `(V22, "v20")`; V4 cannot reserve V23 on top of a broken V22 decode. |
| `src/simulation/journal.py` | `_decode_event_details` imported from `simulation.serialization` (line 41) | Detail decoding is already V22-aware; only the version gate and import need repair. |
| `src/persistence/readers.py` | `event_from_orm` (line 138) | SQL reads rebuild events through the journal codec, so the V22 gate affects database-backed replay. |
| `src/simulation/serialization.py` | `_decode_event_details` (line 6129), `_decode_world_event` (line 7789) | Authoritative detail-version dispatch; do not duplicate kind gates in `journal`. |
| `src/world/events.py` | `EVENT_SCHEMA_REPLAY_V22` (line 89), accepted sets (90-141) | Current maximum event schema is 22. |
| `src/simulation/persistence.py` | `ACCEPTED_EVENT_SCHEMA_VERSIONS` (112), `ACCEPTED_PERSISTENCE_CODEC_VERSIONS` (139), `checkpoint_schema_for_production` (254) | Current codec maximum is `v20`; write-pair selection is feature-based. |
| `src/simulation/compatibility.py` | `_MATRIX` (217), `CompatibilityEntry` (201), `ALEMBIC_HEAD_REVISION` | The compatibility matrix is the single declarative version record. |
| `src/analysis/specifications.py` | `METRIC_FAMILY_COUNT = 136` (53), `MetricFamilyId` (75) | Metric catalog pin for the baseline inventory. |
| `src/observer/version.py` | `OBSERVER_PROTOCOL_VERSION`, `SEMANTIC_EVENT_TYPES` | Protocol and semantic-type pins for the baseline inventory. |
| `src/simulation/runner_models.py` | `RUNNER_SCHEMA_VERSION_V55` (149), `SUPPORTED_RUNNER_SCHEMA_VERSIONS` (151-209) | The baseline runner version set. |
| `src/experiments/civilization_benchmark_models.py` | `V3_BENCHMARK_SCENARIO_COUNT = 30` (26) | V3 benchmark registry pin. |
| `tests/architecture/test_path_dependence_boundaries.py` | `test_v3_38_preserves_current_contract_pins` (79), `test_no_new_runner_or_replay_schema_files` (89-92) | Existing pin test that explicitly forbids `runner-config-v56`; V4 must update it deliberately. |
| `docs/configuration.md` | lines 305-309 | States "There is no `runner-config-v56`"; V4-01 supersedes that statement and must say so. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/simulation/journal.py` | modify | Accept V22 in the journal event decoder. |
| `tests/unit/test_journal_v22_round_trip.py` | create | Prove V22 persistence and ORM-shaped decoding. |
| `tests/architecture/test_v3_baseline_inventory.py` | create | Freeze the V3 completion inventory and validate the compatibility matrix. |
| `docs/v4-architecture.md` | create | Human decision record: authority model, context map, scale/version/migration posture, non-goals. |
| `src/simulation/v4_architecture.py` | create | Machine-readable context registry and validators. |
| `src/simulation/__init__.py` | modify | Export the registry surface. |
| `tests/architecture/test_v4_context_registry.py` | create | Registry, doc parity, and authority invariants. |

## Task 1: Repair and pin the V3 completion baseline

### Intent

V4 version reservations must start from a decoder that can actually read the
current V3 write pair. The V22 journal gap is a latent corruption path: a
contact-enabled run persisted through PostgreSQL cannot be rebuilt through
`event_from_orm`. Repair it first, then freeze the complete V3 pin inventory so
later V4 phases cannot silently drift a count, version, or registry length.

### Implementation Steps

1. In `src/simulation/journal.py`, add `EVENT_SCHEMA_REPLAY_V22` to the
   `from world.events import (...)` block, keeping imports alphabetically grouped
   with the existing `V21` entry.
2. Change the decoder gate in `_decode_world_event` from
   `EVENT_SCHEMA_REPLAY_V2 <= schema_version <= EVENT_SCHEMA_REPLAY_V21` to
   `<= EVENT_SCHEMA_REPLAY_V22`. Do not change the detail dispatch: it already
   delegates to `simulation.serialization._decode_event_details`, which owns the
   V22 contact kinds.
3. Leave `verify_tick_events` untouched. It has no production callers and its
   V2-V5 window is a legacy artifact; record that fact in the new test module
   docstring rather than deleting the function in this plan.
4. Create `tests/unit/test_journal_v22_round_trip.py`:
   - Reuse the event construction helper style from
     `tests/unit/test_contact_events.py` to build one valid contact event with
     `schema_version=EVENT_SCHEMA_REPLAY_V22`
     (`ContactRecorded` or the helper that test already uses).
   - Assert `decode_persistence(encode_persistence(event), WorldEvent) == event`.
   - Build a `WorldEventOrm` instance in memory (no database session) with the
     same field values, call `persistence.readers.event_from_orm`, and assert the
     decoded event equals the source.
   - Assert a V21 event still decodes and a V23 event is rejected with
     `unsupported_version`.
5. Create `tests/architecture/test_v3_baseline_inventory.py` with a frozen
   `V3_BASELINE` mapping and assertions:
   - `RUNNER_SCHEMA_VERSION == "runner-config-v4"`,
     `RUNNER_SCHEMA_VERSION_V55 == "runner-config-v55"`,
     `"runner-config-v56" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS`.
   - `RUNNER_RESULT` pins: `RESULT_SCHEMA_VERSION_V3 == "runner-result-v3"`.
   - Event/codec pins: `EVENT_SCHEMA_REPLAY_V22 == 22`,
     `"v20" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS`, and `"v21" not in`.
   - `METRIC_FAMILY_COUNT == 136`, `len(SEMANTIC_TYPE_BY_KIND) == 73`,
     `OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"`,
     `ALEMBIC_HEAD_REVISION == "0017"`.
   - `BENCHMARK_SCENARIO_COUNT == 16` and `V3_BENCHMARK_SCENARIO_COUNT == 30`.
   - Matrix integrity: every `CompatibilityEntry.write_version` is present in
     `accepted_restore`, entry ids equal their dict keys, and every entry has a
     non-empty `owner_package` and `bump_trigger`.
   - A registry integrity check: every declared V1/V2/V3 benchmark id resolves
     through its registry accessor.
6. Update `tests/architecture/test_path_dependence_boundaries.py` only if a
   baseline assertion there becomes factually wrong in this phase. It must stay
   green unchanged in Phase 1; Task 5 owns the deliberate v56 change.

### Required Interfaces and Contracts

- `simulation.journal._decode_world_event` accepts
  `EVENT_SCHEMA_REPLAY_V2 .. EVENT_SCHEMA_REPLAY_V22`.
- No change to `EVENT_SCHEMA_REPLAY_V22`, `ACCEPTED_EVENT_SCHEMA_VERSIONS`,
  `ACCEPTED_PERSISTENCE_CODEC_VERSIONS`, or `checkpoint_schema_for_production`.
- `V3_BASELINE` is a test-local constant, not a new production API.
- Error codes remain stable: `unsupported_version` for out-of-window versions.

### Requirement Evidence

- Original Request: "Preserve all V1–V3 invariants" and "event versioning".
- `src/simulation/persistence.py` selects `(V22, "v20")` for contact runs.
- `src/persistence/readers.py:138` rebuilds events through the journal codec.
- `.ai-factory/ARCHITECTURE.md` "Versioned Extension Contract" requires legacy
  decoding to be preserved and every new write version to keep working.

### Error Handling and Logging

- Decoding failures keep raising `PersistenceSerializationError` with the same
  codes and paths; no new exception type.
- The test may `DEBUG` log `journal_v22_round_trip_ok event_type=<kind>`, but
  production logging is unchanged. Never log event details or payload content.

### Tests

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_journal_v22_round_trip.py tests/architecture/test_v3_baseline_inventory.py -q`
- Coverage enabled through the repository's configured `addopts`; do not pass
  `--no-cov`.

### Acceptance Criteria

- A V22 contact event round-trips through `encode_persistence` / `decode_persistence`.
- The same event rebuilt from a `WorldEventOrm` row equals the source event.
- V23 is rejected with `unsupported_version`.
- The baseline inventory test fails if any pinned count, version, or matrix
  invariant changes.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_journal_v22_round_trip.py tests/architecture/test_v3_baseline_inventory.py -q`
- Expected result: all selected tests pass, 0 failures, 0 errors, 0 skips.

## Task 2: Author the V4 architecture decision record

### Intent

Commit the V4 boundary decisions before any schema work, so later tasks implement
a fixed architecture instead of inferring one. This document is the normative
source for context ownership, authority, scale, versioning, migration posture,
and non-goals.

### Implementation Steps

1. Create `docs/v4-architecture.md` with these exact top-level sections, in
   order:
   - `# V4 Architecture: Open-Ended Civilizations`
   - `## Status and scope` — V4-01 is scaffolding only; every V4 capability flag
     is closed, unowned, and fails closed; mechanics land in later V4 plans.
   - `## Authority model` — four authorities: `objective_world`,
     `owner_scoped`, `detached_analysis`, `presentation_only`; state that only
     `WorldEngine` mutates objective state and that no organization, market,
     polity, institution, or civilization is an actor.
   - `## Context map` — the thirteen-context table (same rows as the machine
     registry; see Task 3) with columns: Context, Capability flag, Authority,
     Owning packages, Existing mechanism, Event strategy, Measurement.
   - `## Cross-context contracts` — owner-scoped constructs travel only through
     ordinary commands, perception, records, and addressed communication;
     analysis never feeds cognition; clients never write.
   - `## Scale model` — deterministic partitioning, bounded per-tick work,
     order preservation, no thread/async reordering, benchmark-only capacity
     claims.
   - `## Version surfaces` — runner config, runner result, event schema, codec,
     observer protocol, layout schema, metric catalog, Alembic head, command
     count, semantic-type count; each with current pin and owner.
   - `## Compatibility and deprecation policy` — additive-first; exact-key
     versions; legacy decode; dual-read window; the reserved write pairs.
   - `## Migration posture` — no migration in V4-01; ordered stages with
     evidence triggers; Alembic stays `0017`.
   - `## Presentation policy` — read-only clients, additive `/version`
     capabilities, no `observer-protocol-v2` served yet, multi-scale is
     presentation-only.
   - `## Non-goals` — the source-request exclusions plus: no new command, event,
     semantic type, metric family, migration, API version, or global registry;
     no forced social outcome.
   - `## Downstream V4 plan checklist` — what V4-02+ must do before enabling any
     flag: declare the context's event strategy, metric families, observer rows,
     migration need, replay proof, and null-capable tests.
2. In the context table, use exactly these context identifiers so Task 3 can
   machine-check parity: `organizations`, `formal_rules`, `legal_disputes`,
   `diplomacy`, `organized_conflict`, `infrastructure_networks`,
   `supply_chains`, `markets_credit`, `science`, `epidemics`,
   `ecological_feedback`, `disasters`, `societal_resilience`.
3. Add one `### <context-id>` heading plus one short paragraph per context
   describing what is objective, what is owner-scoped, and what is explicitly
   not created. No other `###` headings may appear in the document, so the
   count is exactly thirteen.
4. Link the page from `README.md` (documentation index) and from
   `docs/architecture.md` under its `## See also` section. Use relative links
   only.

### Required Interfaces and Contracts

- Context identifiers are stable ASCII lowercase snake_case.
- The document must not promise behavior: no sentence may assert that an
  organization, market, polity, law, war, epidemic, or collapse will emerge.
- The document must state that `institutional_economy` and
  `multi_hop_testimony_tracking` remain unowned from V3 and are not silently
  claimed by V4.

### Requirement Evidence

- Original Request: "Define: new bounded contexts", "Preserve all V1–V3
  invariants", "organizations/institutions/civilizations must not become magical
  actors".
- `.ai-factory/ARCHITECTURE.md` "Key Principles" and "Versioned Extension
  Contract".
- `.ai-factory/RULES.md` axioms 1, 3, 5, 6.

### Error Handling and Logging

- Documentation only; no runtime logging.
- Link-check failures are build errors, not warnings.

### Tests

- Documentation is verified structurally in Task 3 through
  `tests/architecture/test_v4_context_registry.py` (every registry context id
  appears in the page; every required heading exists).
- Link verification command: `python - <<'PY'` script that resolves every
  relative Markdown link in the touched pages; expected 0 broken links.

### Acceptance Criteria

- `docs/v4-architecture.md` exists with the required sections and all thirteen
  context ids.
- `README.md` and `docs/architecture.md` link to it.
- No relative link is broken.

### Verification

- `grep -c '^### ' docs/v4-architecture.md` returns the expected context-section
  count (thirteen).
- Relative-link check exits 0.

## Task 3: Add the machine-readable V4 context registry

### Intent

Turn the context map into an importable, validated contract so V4-02+ plans can
assert ownership instead of restating it, and so V4-01 can prove that no context
claims authority it does not own.

### Implementation Steps

1. Create `src/simulation/v4_architecture.py` with:
   - `V4_CONTEXT_MAP_VERSION: Final[str] = "v4-context-map-v1"`.
   - `V4ContextId(StrEnum)` with the thirteen identifiers from Task 2.
   - `V4Authority(StrEnum)` with `OBJECTIVE_WORLD`, `OWNER_SCOPED`,
     `DETACHED_ANALYSIS`, `PRESENTATION_ONLY`.
   - `V4ContextSpec` frozen slots dataclass with fields:
     `context_id: V4ContextId`, `capability_flag: str | None`,
     `authority: V4Authority`, `owner_packages: tuple[str, ...]`,
     `existing_mechanism: str`, `required_config_seam: str`,
     `uses_existing_events: bool`,
     `prerequisite_contexts: tuple[V4ContextId, ...]`,
     `non_goals: tuple[str, ...]`.
   - `V4_CONTEXTS: Final[tuple[V4ContextSpec, ...]]` with the thirteen rows.
   - `V4_CONTEXT_BY_ID: Final[Mapping[V4ContextId, V4ContextSpec]]`.
   - `V4_ANALYSIS_ONLY_CONTEXTS: Final[frozenset[V4ContextId]]` containing only
     `societal_resilience`.
   - `validate_v4_contexts() -> None` raising `ValueError` with stable codes:
     `v4_context_duplicate`, `v4_context_flag_duplicate`,
     `v4_context_unknown_owner`, `v4_context_analysis_authority`,
     `v4_context_analysis_flag`, `v4_context_prerequisite_cycle`,
     `v4_context_missing_non_goals`, `v4_context_reserved_flag`.
   - `v4_context_for_flag(flag: str) -> V4ContextSpec`; unknown flags raise
     `ValueError("v4_context_unknown_flag")`, and no analysis-only flag exists.
   - `v4_owner_packages() -> frozenset[str]`.
2. Context rows (authority and owner are fixed by this plan; `prerequisites`
   names contexts that must be owned first):
   - `organizations` — `OWNER_SCOPED`; `agents.cognition`, `social`,
     `simulation`; prerequisites: none; existing
     `collective_projects`/`public_goods`/`mentorship`; reuses events; no global
     organization actor or automatic resource pool.
   - `formal_rules` — `OWNER_SCOPED`; `agents.cognition`, `simulation`;
     prerequisites: none; existing norms/conventions/durable records; reuses
     events; no world-law object.
   - `legal_disputes` — `OWNER_SCOPED`; `agents.cognition`, `simulation`;
     prerequisites: `formal_rules`; existing `mediation`; reuses events; no
     court or binding verdict.
   - `diplomacy` — `OWNER_SCOPED`; `agents.cognition`, `social`, `simulation`;
     prerequisites: `organizations`; existing
     `cultural_contact`/`regions_migration`/commitments; reuses events; no
     polity or treaty authority.
   - `organized_conflict` — `OBJECTIVE_WORLD`; `world`, `simulation`,
     `agents.cognition`; prerequisites: `diplomacy`; existing physical
     harm/attack commands; reuses events; no war state or army actor.
   - `infrastructure_networks` — `OBJECTIVE_WORLD`; `world`, `simulation`;
     prerequisites: none; new physical network graph; reserves a new write pair.
   - `supply_chains` — `OBJECTIVE_WORLD`; `world`, `simulation`; prerequisites:
     `infrastructure_networks`; existing production/storage/transport; reuses
     events; no central planner.
   - `markets_credit` — `OWNER_SCOPED`; `agents.cognition`, `simulation`;
     prerequisites: `supply_chains`, `organizations`; existing
     `resource_exchange_profile`/commitments; reuses events; no money object or
     central bank.
   - `science` — `OWNER_SCOPED`; `agents.cognition`, `simulation`;
     prerequisites: `formal_rules`; existing experimentation/practical
     knowledge/repositories; reuses events; no objective truth registry.
   - `epidemics` — `OBJECTIVE_WORLD`; `world`, `simulation`, `agents.cognition`;
     prerequisites: `infrastructure_networks`; new host/transmission state;
     reserves a new write pair; agents learn only through perception and
     records.
   - `ecological_feedback` — `OBJECTIVE_WORLD`; `world`, `simulation`;
     prerequisites: `supply_chains`; existing resource regeneration/depletion;
     reserves a new write pair; no ecological actor.
   - `disasters` — `OBJECTIVE_WORLD`; `world`, `simulation`; prerequisites:
     `ecological_feedback`; existing environmental hazards; reserves a new
     write pair; no disaster actor.
   - `societal_resilience` — `DETACHED_ANALYSIS`; `analysis`; prerequisites:
     none; `capability_flag` is `None`; new detached classification; reuses
     existing evidence; no feedback into cognition.
3. Validation rules:
   - Exactly thirteen specs; ids unique; every non-analysis context has
     exactly one unique flag, and the analysis-only context has
     `capability_flag is None`.
   - `owner_packages` is a non-empty subset of
     `{world, simulation, agents.cognition, memory, social, analysis,
     experiments, observer, api, persistence, research_runner}`.
   - Every `DETACHED_ANALYSIS` context is listed in
     `V4_ANALYSIS_ONLY_CONTEXTS`, owns only `analysis`, has no capability flag,
     and does not own a mutable world seam.
   - `world` appears in `owner_packages` if and only if the authority is
     `OBJECTIVE_WORLD`; `analysis` appears only for `DETACHED_ANALYSIS`
     contexts, which own no other package.
   - For every flagged context, `required_config_seam` equals
     `v4_capability_flags.<flag>`; the analysis-only context uses
     `analysis_capture`.
   - Prerequisites form a DAG over known context ids; self-references and
     unknown targets are rejected.
   - Every spec has at least one non-goal.
   - Flags may not use the reserved V3 names.
4. Export the registry from `src/simulation/__init__.py` following the existing
   grouped facade style, and extend its alphabetical `__all__`.
5. Create `tests/architecture/test_v4_context_registry.py`:
   - `validate_v4_contexts()` passes.
   - Thirteen contexts, twelve flags, stable declaration order.
   - `societal_resilience` is the only analysis-only context and its
     `capability_flag` is `None`; `v4_context_for_flag` raises for an
     analysis-only or unknown flag string.
   - The prerequisite edge set equals the declared map and is acyclic.
   - Every flagged context's `required_config_seam` matches its flag, and the
     analysis-only context's seam is `analysis_capture`.
   - Every context id appears verbatim in `docs/v4-architecture.md`.
   - All required headings from Task 2 exist.
   - No spec claims `world` ownership without `OBJECTIVE_WORLD`.
   - `simulation/v4_architecture.py` imports no `experiments`, `analysis`,
     `api`, `persistence`, `infrastructure`, or `observer` module (AST check).
   - A deliberately broken copy (duplicate flag, cycle, analysis context owning
     `world`, analysis context with a flag) raises the documented error code.

### Required Interfaces and Contracts

- `V4ContextSpec` is frozen and slotted; no mutable defaults.
- `V4_CONTEXTS` order is the canonical publication order; later plans must not
  reorder it without a version bump of `V4_CONTEXT_MAP_VERSION`.
- `V4ContextId` values equal the documented identifiers exactly.
- Importing `simulation.v4_architecture` has no side effects and no logging.

### Requirement Evidence

- Original Request: "Define: new bounded contexts".
- `.ai-factory/ARCHITECTURE.md` dependency table and "No scripted civilization"
  principle.
- `tests/architecture/boundary_checker.py` allowlist model.

### Error Handling and Logging

- Validation is pure and deterministic; failures raise `ValueError` with the
  stable codes above and no partial mutation.
- No logging at import. Callers may log metadata (`context_count=13`) at DEBUG.

### Tests

- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_v4_context_registry.py -q`

### Acceptance Criteria

- The registry validates and is exported from `simulation`.
- The doc/registry parity test passes.
- Every authority assignment matches the Phase 1 table.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/architecture/test_v4_context_registry.py -q`
- Expected result: all tests pass, 0 failures.
- `uv run --frozen --python 3.12.14 lint-imports` still reports 25 contracts kept.

## Phase Risks and Mitigations

- Risk: repairing the journal V22 gate changes persisted V3 behavior.
  Mitigation: the change only widens an accepted version; legacy V21 and all
  other gates stay identical, and the round-trip test proves equality.
- Risk: the context registry becomes a second source of truth that drifts from
  the document.
  Mitigation: the doc-parity test reads `docs/v4-architecture.md` and requires
  every registry id; Task 16 re-runs it after documentation edits.
- Risk: a context accidentally claims world authority.
  Mitigation: the validator rejects `world` ownership for non-objective
  authorities and rejects analysis-only contexts with mutable seams.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
