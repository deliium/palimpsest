# Phase 7: Invariants and Pins

Plan: [index.md](index.md)
Tasks: 20
Depends on: Phase 1-6 / Tasks 1-19

## Objective

Enforce the complete V4-23 architectural contract in executable invariants: no
new V4 context/flag/runner schema/command/event/observer semantic type/write
pair/migration, `organizations` remains the owning context, the catalog is
append-only at 220, and every pin is asserted in one place.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `tests/architecture/test_credit_relationships_invariants.py` | 48-64 baseline hash; 67-90 no-bump; 104-113 context authority; 222-230 unowned guard | Invariant template. |
| `tests/architecture/test_credit_relationships_boundaries.py` | AST import boundaries | Boundary template. |
| `tests/architecture/test_v4_architecture_invariants.py` | 171-210 counts | Shared V4 invariants. |
| `tests/architecture/test_v4_context_registry.py` | 99-104 | Registry invariants. |
| `src/simulation/v4_architecture.py` | `organizations` 110-127; `_REQUIRED_CONTEXT_COUNT` 56; `V4_CONTEXT_MAP_VERSION` 38 | Context authority anchor. |
| `src/simulation/compatibility.py` | `V4_OWNED_CAPABILITY_FLAGS` 155-166 | Ownership anchor. |
| `src/simulation/runner_models.py` | `_V4_OWNED_CAPABILITY_FLAGS` 328-339; `V4CapabilityFlags` 1128-1179 | Private ownership mirror. |
| `src/analysis/specifications.py` | 53; 286-293; 9733; 9946-9949 | Catalog append anchor. |
| `tests/unit/test_alembic_head_pin.py` | 18-24 | Migration head pin. |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `tests/architecture/test_accounting_ledgers_invariants.py` | create | V4-23 structural invariants. |
| `tests/architecture/test_accounting_ledgers_boundaries.py` | create | AST import boundaries. |
| `tests/unit/test_accounting_ledgers_pins.py` | modify (created in Task 11) | Complete pin set. |
| `tests/architecture/test_v4_architecture_invariants.py` | modify only if a shared count assertion must name V4-23 | Keep counts; add a V4-23 reference without changing 14/12/8/4. |

---

## Task 20: Enforce architecture invariants and pin sweeps

### Intent

Make every non-negotiable V4-23 decision fail a test if a later change violates
it, and produce the final pin sweep that Task 23 certifies.

### Implementation Steps

1. `tests/architecture/test_accounting_ledgers_invariants.py`:
   - `len(V4_CONTEXTS) == 14`, `len(V4_CAPABILITY_FLAGS) == 12`,
     owned set has 8 names, unowned set is exactly
     `{science, epidemics, ecological_feedback, disasters}`.
   - `organizations` remains `OWNER_SCOPED` with owner packages
     `("agents.cognition", "social", "simulation")`, `uses_existing_events=True`,
     prerequisites `()`, and its non-goals unchanged.
   - No `runner-config-v57` constant, accepted schema, or decode branch exists.
   - `METRIC_FAMILY_COUNT == 220`; `specs[216:220]` exact ids; SHA-256 baseline
     of the first 216 unchanged.
   - Commands 43; observer semantic types 73; replay-v27/codec `v25`; Alembic
     `0017`; `/v1`; `observer-protocol-v1`.
   - No accounting symbol in `src/observer` or in observer semantic catalogs.
   - No accounting field named `truth`, `verified`, `canonical_ledger`,
     `audited`, `objective_balance`, `book_value`, `solvent`, `credit_score`,
     `money`, `currency`, `price`, `interest`, `reconciled`, or `fraud`.
2. `tests/architecture/test_accounting_ledgers_boundaries.py`:
   - `src/agents/cognition/accounting_ledgers*.py` imports only public domain
     facades and no `simulation`, `analysis`, `api`, `experiments`,
     `persistence`, or `infrastructure`;
   - `src/world/accounting_ledgers.py` imports only `world` internals allowed by
     the existing world boundary;
   - `src/analysis/accounting_ledgers_*.py` imports no cognition ledger, no
     `simulation`, `experiments`, `api`, `persistence`, or `infrastructure`;
   - `src/simulation/accounting_ledgers_*.py` imports no `analysis`, `api`,
     `experiments`, `persistence`, or `observer`;
   - `src/persistence/accounting_ledgers_filesystem.py` imports no `analysis`;
   - `src/api/routes/accounting_ledgers.py` imports no `analysis`;
   - Python never imports either client.
3. `tests/unit/test_accounting_ledgers_pins.py`: complete the pin set
   (created in Task 11) with:
   - policy versions (`accounting-ledgers.v1`,
     `accounting-ledgers-communication.v1`);
   - snapshot/store version strings;
   - seven route paths;
   - both settings names;
   - no CLI producer;
   - the allowed reason codes.
4. Update any shared V4 invariant test that enumerates owned flags so it still
   asserts exactly 8 and includes `organizations` and `markets_credit`.
5. Emit no logging (test-only).

### Required Interfaces and Contracts

- Invariants are pure assertions over imported modules/constants; no network,
  Docker, or filesystem outside `tmp_path`.
- No test asserts an implementation detail that a legitimate future V4-24 would
  need to change (for example, do not assert the total number of V4 plans).
- Shared counts remain 14/12/8/4.

### Requirement Evidence (when reconciliation applies)

- `.ai-factory/ARCHITECTURE.md` "Versioned Extension Contract",
  "Capability ownership", and "Anti-Patterns".
- `.ai-factory/RULES.md` axioms 1-5.

### Error Handling and Logging

- Not applicable.

### Tests

Commands:
- `uv run pytest tests/architecture/test_accounting_ledgers_invariants.py tests/architecture/test_accounting_ledgers_boundaries.py -q`
- `uv run pytest tests/unit/test_accounting_ledgers_pins.py -q`
- `uv run pytest tests/architecture/test_v4_architecture_invariants.py tests/architecture/test_v4_context_registry.py -q`
- `uv run lint-imports`

### Acceptance Criteria

- Every non-negotiable V4-23 decision is guarded by a test.
- The pin set is complete and consistent.
- No existing V4 invariant regresses.

### Verification

- The four commands above — expected: all pass; import contracts 25 kept /
  0 broken.

## Phase Risks and Mitigations

- Risk: a boundary test becomes a copy of the source and drifts.
  Mitigation: assert package-level import allowlists, not line-level content.
- Risk: the first-216 baseline hash is brittle against whitespace.
  Mitigation: hash the canonical serialized spec values, not file text.
- Risk: a new V4-23 test accidentally forbids a legitimate V4-24.
  Mitigation: assert only this plan's non-goals, not global freeze.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
