# Phase 7: Invariants and Pins

Plan: [index.md](index.md)
Task: 22
Depends on: Phase 6 / Tasks 19-21 and all earlier tasks

## Objective

Freeze the architectural invariants and every version pin that V4-21 must not
move, and add positive/negative architecture tests proving the feature is
owner-scoped, analysis-detached, and free of any global price authority.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/simulation/v4_architecture.py` | `_REQUIRED_CONTEXT_COUNT` 56, `markets_credit` 212-228, `validate_v4_contexts` 367-417 | Context/flag counts and owned seam |
| `src/simulation/runner_models.py` | `_V4_CAPABILITY_FLAG_NAMES` 307-320, `_V4_OWNED_CAPABILITY_FLAGS` 328-339 | Ownership set stays eight |
| `src/simulation/compatibility.py` | `ALEMBIC_HEAD_REVISION` 118, `V4_OWNED_CAPABILITY_FLAGS` 155-166 | Version pins |
| `src/world/_rules.py` | `COMMAND_RULE_MATRIX` 360 | Command count 43 |
| `src/observer/version.py` | `SEMANTIC_EVENT_TYPES` 11-185 | Observer semantic count 73 |
| `src/simulation/persistence.py` | 113-171 | Replay/codec acceptance |
| `src/simulation/versioning.py` | 42-100 | Reserved write pairs and travel pair |
| `tests/architecture/test_v4_architecture_invariants.py` | 130-161 | Existing pin assertions |
| `tests/architecture/test_market_institutions_invariants.py` | 1-? | Pattern for a V4-20 pipeline invariant suite |
| `tests/unit/test_market_institutions_pins.py` | 26-76 | Suite-wide stale-pin scan pattern |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `tests/architecture/test_emergent_prices_invariants.py` | create | Structural/authority/version invariants |
| `tests/architecture/test_emergent_prices_boundaries.py` | extend | Import, route, and layer boundaries |
| `tests/unit/test_emergent_prices_pins.py` | modify | Add final pins |
| `tests/architecture/test_v4_architecture_invariants.py` | modify | Assert V4-21 adds no context/flag |
| `tests/unit/test_metric_specifications.py` | modify | 212 catalog pin |
| Existing 208 pins | modify | Current-state only |

## Task 22: Enforce architecture invariants and pin sweeps

### Intent

Make it impossible for a later change to reintroduce a global price, a new
flag/schema/command, or a private-state read without failing a named gate.

### Implementation Steps

1. Create `tests/architecture/test_emergent_prices_invariants.py`:
   - `markets_credit` remains `OWNER_SCOPED` with owners
     `("agents.cognition", "simulation")`, `uses_existing_events=True`, and
     prerequisite contexts `(SUPPLY_CHAINS, ORGANIZATIONS)`;
   - context count 14, flag count 12, owned count 8, unowned count 4;
   - `emergent_prices` adds no `V4ContextId`, `V4CapabilityFlag`, context entry,
     or prerequisite edge;
   - no `runner-config-v57` string in `src/` or `tests/`;
   - no Alembic `0018` file and `ALEMBIC_HEAD_REVISION == "0017"`;
   - `len(COMMAND_RULE_MATRIX) == 43`, `len(get_args(AgentCommand)) == 43`;
   - `len(SEMANTIC_EVENT_TYPES) == 73`;
   - `max(ACCEPTED_EVENT_SCHEMA_VERSIONS) == 27`,
     `"v25" in ACCEPTED_PERSISTENCE_CODEC_VERSIONS`,
     `"v22" not in ACCEPTED_PERSISTENCE_CODEC_VERSIONS`;
   - `METRIC_FAMILY_COUNT == 212` and the `_BASELINE_208_DIGEST` over the first
     208 specs is unchanged.
2. Add authority invariants:
   - `simulation` never imports `analysis`;
   - `analysis.emergent_prices_*` imports no `agents`, `persistence`, `observer`,
     `api`, or `experiments`;
   - `api.routes.emergent_prices` imports no `analysis` or `experiments`;
   - no cognition module imports `analysis`;
   - no `WorldState`/`WorldEvent`/runtime/store/API type appears in analysis
     signatures.
3. Add negative content guards:
   - no dataclass field in `emergent_prices*` modules is named `price`,
     `canonical_price`, `price_index`, `clearing_price`, `rate`, `money`,
     `currency`, `numeraire`, `bid`, `ask`, `spread`, `fee`, `commission`,
     `tax`, `debt`, `credit_limit`, `market_score`, `ranking`, `severity`,
     `recommendation`, `allocation`, `quota`, `central_planner`;
   - no agent id, entity id, ledger id, or event id field exists in analysis or
     snapshot row types;
   - no `mktc-`/`mkt-ven-` minting helper exists in `emergent_prices` modules
     (V4-20 owns those identities);
   - every distribution row/record has `bin_shares_milli` of length 5 summing to
     1000 when `status=available`, and `sample_source` stays in
     `{completed, quoted}`;
   - no Godot source file mentions `emergent_prices`.
4. Extend `tests/architecture/test_emergent_prices_boundaries.py`:
   - seven GET-only route decorators and `EMERGENT_PRICES_ROUTE_COUNT == 7`;
   - settings names use the `PALIMPSEST_` prefix only;
   - no new observer capability or protocol string;
   - public snapshot/export symbols are importable from the `simulation` facade.
5. Update `tests/unit/test_emergent_prices_pins.py` with the final pins:
   `43` commands, `73` semantics, `212` families, `14/12/8/4` V4 counts,
   replay-v27/codec `v25`, Alembic `0017`, `/v1`, `observer-protocol-v1`.
6. Sweep remaining `== 208` current-state code/test assertions to `212`;
   leave documentation files and docs-parity tests to Task 24 and keep
   historical prefix digests over the first 208 families.
7. Assert `emergent_prices@1` is in `OFF_GATE_MATRIX_EXPERIMENT_IDS` and absent
   from `EXPERIMENT_A_V1_CONDITION_IDS`.

### Required Interfaces and Contracts

- Every assertion names a concrete module, constant, or AST rule.
- Historical counts in archived plans are not rewritten.
- No test is skipped or xfailed to pass a gate.

### Requirement Evidence

- Versioned extension contract: `.ai-factory/ARCHITECTURE.md` "Versioned
  Extension Contract" and requirement 1-7.
- No global Market/price: user request and
  `src/simulation/v4_architecture.py:224-227`.

### Error Handling and Logging

- Architecture tests emit only assertion messages; no payload dumps.

### Tests

- `uv run pytest tests/architecture/test_emergent_prices_invariants.py
  tests/architecture/test_emergent_prices_boundaries.py tests/unit/test_emergent_prices_pins.py -q`
- `uv run pytest tests/unit tests/architecture -q`

### Acceptance Criteria

- All invariants and pins pass with no weakened gate.
- Any future global price/flag/schema/command change fails a named test.

### Verification

- `uv run pytest tests/unit tests/architecture -q`
- Expected: all pass.

## Phase Risks and Mitigations

- Risk: AST guards become brittle across formatting.
  Mitigation: parse with `ast`, not text matching, for imports and dataclass
  fields.
- Risk: pin sweep touches historical regression tests.
  Mitigation: only current-state assertions change; prefix digests remain.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
