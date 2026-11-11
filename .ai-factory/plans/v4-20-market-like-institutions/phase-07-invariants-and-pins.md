# Phase 7: Invariants and Pins

Plan: [index.md](index.md)
Task: 22
Depends on: Tasks 1-21

## Objective

Enforce the V4 boundaries, authority separation, closed vocabulary, and every
global pin touched by V4-20. This phase is the single place where a missing
sweep or an accidental schema/authority change must fail.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `tests/architecture/test_v4_architecture_invariants.py` | pins (125-165), ownership (167-216), reservations (230-244) | Existing V4 invariant suite to extend |
| `tests/architecture/test_trade_networks_boundaries.py` | import/authority/vocabulary scans (70-183) | Boundary test pattern |
| `tests/architecture/test_supply_chain_invariants.py` | pins and ownership | Sibling invariant pattern |
| `src/simulation/v4_architecture.py` | registry (109-320), validation (367-417) | Context and flag counts |
| `src/simulation/versioning.py` | reservations (42-115) | Write-pair invariants |
| `src/simulation/compatibility.py` | accepted replay/codec/runner pins | Version pins |
| `src/observer/version.py` | semantic type count | Observer pin |
| `src/analysis/specifications.py` | `METRIC_FAMILY_COUNT` (53) | Catalog pin |
| `src/api/routes/market_institutions.py` | `MARKET_INSTITUTIONS_ROUTE_COUNT` | Route pin |
| `clients/research-ui/src/research/selection.ts` | view registry | Client pin |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `tests/architecture/test_market_institutions_boundaries.py` | create | Import, authority, vocabulary, and client scans |
| `tests/architecture/test_market_institutions_invariants.py` | create | Global pins and ownership |
| `tests/architecture/test_v4_architecture_invariants.py` | modify | Only if Task 12 left a pin unadjusted |

## Task 22: Enforce architecture invariants and pin sweeps

### Intent

Make each cross-cutting decision executable: 14 contexts / 12 flags / 8 owned,
no v57, no new write pair, no analysis authority leak, no commercial vocabulary,
seven read routes, and no Godot overlay.

### Implementation Steps

1. Create `tests/architecture/test_market_institutions_boundaries.py`:
   - scan `src/analysis/market_institutions_*.py` imports and assert they never
     import `api`, `persistence`, `experiments`, `observer`, `agents.cognition`,
     or `world._*`; allowed imports are public `world`/`simulation` contracts;
   - scan `src/agents/cognition/market_institutions*.py` and assert no import of
     `analysis`, `api`, `persistence`, `experiments`, `observer`,
     `WorldState`, `WorldEngine`, `ActionSubmission`, `TickToken`, or event
     store;
   - assert no `class .*Command` or `class .*Event` definition exists in any new
     module;
   - assert `market_institutions_actions.py` returns only an existing command
     and contains no `submit`, `resolve`, `execute`, or `teleport` call;
   - scan new Python dataclass field names, function/keyword parameter names, API
     schema field names, and client-rendered strings for forbidden commercial
     keys (`price`, `money`, `currency`, `numeraire`, `clearing_price`, `bid`,
     `ask`, `spread`, `fee`, `commission`, `tax`, `debt`, `credit_limit`,
     `market_score`, `ranking`, `severity`, `recommendation`, `allocation`,
     `quota`, `central_planner`, `volume`, `turnover`, `liquidity`); do not
     literal-scan `src/analysis/market_institutions_contract.py`, which must
     declare those keys as `MARKET_FORBIDDEN_KEYS`, and do not scan the test
     file that defines the expected list;
   - scan `src/api/routes/market_institutions.py` and assert every route
     decorator is `@router.get`, the route count is 7, and the capability is
     `SUBJECTIVE_DEBUG`;
   - scan `clients/research-ui/src` and assert the only `method: 'POST'` remains
     `api/client.ts`;
   - scan `clients/godot-observer/` for `market-institutions`, `marketInstitutions`,
     or `mkt-` presentation tokens and assert no match (no overlay).
2. Create `tests/architecture/test_market_institutions_invariants.py`:
   - `V4_CONTEXT_MAP_VERSION == "v4-context-map-v2"`;
   - `len(V4_CONTEXTS) == 14`, `len(V4_CAPABILITY_FLAGS) == 12`;
   - `V4_OWNED_CAPABILITY_FLAGS` equals the eight owned names including
     `markets_credit`;
   - `markets_credit` is in `V4_EVENT_REUSING_CONTEXTS` and in no
     `V4_WRITE_PAIR_RESERVATIONS` entry;
   - `[item.event_schema for item in V4_DEEPENING_WRITE_PAIRS] == [27]` and
     codecs `["v25"]`;
   - `METRIC_FAMILY_COUNT == 208`; first 204 spec digest unchanged; last four
     families are the market families in order;
   - `len(COMMAND_RULE_MATRIX) == 43` and `len(SEMANTIC_EVENT_TYPES) == 73`;
   - `max(ACCEPTED_EVENT_SCHEMA_VERSIONS) == 27`; `"v25"` accepted; `"v22"`
     not accepted;
   - `RUNNER_SCHEMA_VERSION == "runner-config-v4"`, v55 and v56 supported, and
     no `runner-config-v57` string in `src/` or `tests/` except a negative
     assertion;
   - `MARKET_INSTITUTIONS_ROUTE_COUNT == 7`;
   - Alembic head `0017`, `/v1`, `observer-protocol-v1` unchanged;
   - `validate_v4_contexts()`, `validate_write_pair_reservations()`, and
     `validate_metric_catalog()` all pass.
3. Update `tests/architecture/test_v4_architecture_invariants.py` only if a pin
   from Task 12 is still literal; the final state must name the eight owned flags
   and 208 families.
4. Run the import-linter contracts and fix any new contract break by adding the
   new modules to the existing allowed layers, not by weakening a contract.
5. Verify the complete pin set with targeted commands before moving to docs.

### Required Interfaces and Contracts

- No new bounded context, capability slot, write pair, codec marker, replay
  marker, observer semantic type, API version, or Alembic revision exists.
- `market_institutions` owns no `world` state and no `analysis` authority in the
  registry; the registry entry stays exactly as declared in V4-01.
- Analysis remains read-only and client code remains GET-only.
- Every pin is expressed once in a test that names the current value; no pin is
  inferred from another test's constants.

### Requirement Evidence

- `.ai-factory/ARCHITECTURE.md` "Versioned Extension Contract" and
  "Requirements for later changes" 1-7.
- `src/simulation/v4_architecture.py:212-228` — the declared context this plan
  owns.
- `tests/architecture/test_v4_architecture_invariants.py:230-244` — reservation
  and prerequisite invariants.

### Error Handling and Logging

- Architecture failures list file paths and matched tokens only.
- No production logging changes.

### Tests

- `tests/architecture/test_market_institutions_boundaries.py`
- `tests/architecture/test_market_institutions_invariants.py`
- `uv run lint-imports`

### Acceptance Criteria

- The new architecture suites pass with zero offenders.
- `uv run lint-imports` reports all contracts kept.
- No source or test file outside the plan's declared exceptions mentions
  `runner-config-v57`.

### Verification

- `uv run pytest tests/architecture -q`
- `uv run lint-imports`
- Expected result: all pass; 25 contracts kept, 0 broken.

## Phase Risks and Mitigations

- Risk: a vocabulary scan produces false positives in historical docs or test
  fixtures. Mitigation: scope the scan to new source/client files and allow the
  existing negative-assertion tests; do not scan archived plans.
- Risk: ownership pins exist in several literal sets.
  Mitigation: Task 12 sweeps them and Task 22 asserts the canonical set plus a
  repository-wide `runner-config-v57` negative scan.
- Risk: the E2E accidentally imports a private world module, hiding an authority
  leak. Mitigation: the boundary scan checks both source modules and the new
  E2E test for private imports.

## Phase Completion Checklist

- Every Task 22 acceptance criterion is verified.
- All global pins match the Definition of Done.
- `index.md` task checkbox is updated immediately after verified completion.
