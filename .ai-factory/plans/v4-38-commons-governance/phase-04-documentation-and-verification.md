# Phase 4: Documentation and verification

Plan: [index.md](index.md)  
Tasks: 8  
Depends on: Phases 1–3

## Objective
Document the exact runtime and research contracts and record what was actually checked.

## Current-Code Evidence

| Path | Symbols / sections | Why it matters |
|---|---|---|
| `docs/overexploitation.md` | Configuration, Controlled demonstration | Adjacent feature and reproduction style |
| `docs/development.md` | Tests | Pinned environment and opt-in lanes |
| `tests/architecture/test_v4_architecture_invariants.py`, `tests/unit/test_v2_scientific_invariants.py` | Architecture and V2 scientific gates | Detect boundary changes and off-path drift |
| `tests/integration/test_overexploitation_durable_replay.py` | V4-37 durable restore/continuation | Existing database-dependent physical replay check |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `docs/commons-governance.md` | Create | Configuration, claims/limits, scenario and reproducible programmatic capture |
| `README.md`, `AGENTS.md`, `docs/{configuration,overexploitation}.md` | Modify | Minimal links and exact v62 gate |
| `.ai-factory/plans/v4-38-commons-governance/index.md` | Modify during implementation/verification | Progress and concise verification receipt |

## Task 8: Document and verify the feature and compatibility gates

### Intent
Publish the v62 seam, ensure the legacy simulator is unchanged, and avoid implying a verification claim for a skipped lane.

### Implementation Steps
1. Run the mandatory docs checkpoint through `$aif-docs`. Add feature page and links. Show the exact new config leaf, inherited combinations, scoped no-authority semantics, what monitoring cannot attribute, and stock/turn/criticism examples. Document default writes, event 29 / `v27` / projector `v2`, pending v7 vs world codec, and unchanged API/UI/migration/metric catalog pins.
2. Include a runnable programmatic example using the two paired definitions, fixed seed matrix, opt-in capture and within-layout replicate/seed comparisons; separate controlled proofs and autonomous reports. State all denominators, distinct missing vs null statuses and that `disasters` remains unowned. Do not mark M8 complete.
3. Run focused and default verification with coverage intact; run a disposable-DB replay lane only if prerequisites are present and record it as unexecuted otherwise. Record command, outcome and coverage in the plan verification receipt. Record unused Compose/Godot/browser/scale lanes as unexecuted or out of scope, not certified.

### Required Interfaces and Contracts
Docs follow `docs/development.md` pin Python `3.12.14`, `uv run --frozen`, no new services or dependencies. Scope-only roadmap linkage is not a roadmap edit. Verification must include unchanged v61/v60 semantics, feature gates and owner analysis isolation.

### Requirement Evidence
Original Request; `.ai-factory/RULES.md` coding and testing standards; `.ai-factory/ARCHITECTURE.md` versioned extension and gate rules.

### Error Handling and Logging
Fix regressions in scope, report environment blockers and do not disable coverage or lower check thresholds. Never print database URLs or captured payloads in the receipt.

### Tests
Run focused commands from earlier phases; check exact example values against tests and confirm the README/link index resolves. Keep default and integration results separate.

### Acceptance Criteria
Reproduction instructions suffice without source spelunking; every planned invariant has passed evidence or an honest named limitation.

### Verification
- `uv run --frozen --python 3.12.14 pytest tests/unit/test_commons_governance_*.py tests/unit/test_overexploitation_*.py tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py tests/unit/test_alembic_head_pin.py tests/architecture/test_v4_architecture_invariants.py -q`
- `uv run --frozen --python 3.12.14 pytest`
- `uv run --frozen --python 3.12.14 ruff check src tests`
- `uv run --frozen --python 3.12.14 mypy src tests`
- `uv run --frozen --python 3.12.14 lint-imports`
- With a validated disposable `palimpsest_test` database configured: `uv run --frozen --python 3.12.14 pytest -m integration tests/integration/test_overexploitation_durable_replay.py -q`

## Phase Risks and Mitigations
- Risk: older summary pins are copied as current. Mitigation: prefer executable compatibility checks and the v61 replay reference when documenting v62.

## Phase Completion Checklist
- [x] Document and verify each contract; index checkbox and verification receipt attached.
