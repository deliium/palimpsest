# Phase 7: Invariants and Pins

Plan: [index.md](index.md)
Task: 20
Depends on: Tasks 1-19

## Objective

Prove structurally that V4-22 deepened `markets_credit` without adding a V4
context, flag slot, runner schema, command, event, observer semantic type, write
pair, `/v2` route, SQL migration, Godot overlay, or global credit registry. All
active pins must agree on eight owned V4 flags and 216 metric families.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/simulation/v4_architecture.py` | 14 contexts, 12 flags, `MARKETS_CREDIT` 212-228 | Ownership and non-goal source |
| `src/simulation/compatibility.py` | `V4_OWNED_CAPABILITY_FLAGS`, `ALEMBIC_HEAD_REVISION` | Ownership and migration pins |
| `src/simulation/versioning.py` | reserved write pairs | No new pair may be claimed |
| `src/simulation/persistence.py` | accepted event schemas and codec versions | No replay/codec bump |
| `src/world/_rules.py` | `COMMAND_RULE_MATRIX` | 43 commands |
| `src/world/actions.py` | `AgentCommand` union | 43 command variants |
| `src/observer/version.py` | `SEMANTIC_EVENT_TYPES`, `OBSERVER_PROTOCOL_VERSION` | 73 semantics and protocol pin |
| `tests/architecture/test_emergent_prices_invariants.py` | 37-120 | Exact V4-21 invariant template |
| `tests/architecture/test_credit_relationships_invariants.py` | created in Task 11 | Extend with structural checks |
| `tests/architecture/test_credit_relationships_boundaries.py` | create | Import/dependency boundaries |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `tests/architecture/test_credit_relationships_invariants.py` | modify | Add structural, ownership, version, and route invariants |
| `tests/architecture/test_credit_relationships_boundaries.py` | create | Import-linter-equivalent AST boundary checks |
| `tests/unit/test_credit_relationships_pins.py` | modify | Add route count, settings, and no-overlay pins |
| `tests/architecture/test_emergent_prices_invariants.py` | no change after Task 11 | Remains the prior-seam regression |
| `src/**` | no change | This task adds tests only unless a pin is stale |

## Task 20: Enforce architecture invariants and pin sweeps

### Intent

Make a future edit fail loudly if it claims a V4 flag, bumps a schema, adds a
command or event, leaks an owner ledger into world authority, or drifts a pin.

### Implementation Steps

1. Extend `tests/architecture/test_credit_relationships_invariants.py`:
   - `len(V4_CONTEXTS) == 14`, `len(V4_CAPABILITY_FLAGS) == 12`,
     `len(V4_OWNED_CAPABILITY_FLAGS) == 8`;
   - owned set exactly `{organizations, formal_rules, legal_disputes,
     diplomacy, organized_conflict, infrastructure_networks, supply_chains,
     markets_credit}`;
   - `markets_credit` authority is `OWNER_SCOPED`, owner packages are
     `("agents.cognition", "simulation")`, `uses_existing_events=True`,
     prerequisites are `(SUPPLY_CHAINS, ORGANIZATIONS)`, and non-goals still
     include "no central bank or enforced debt";
   - no `credit`/`credit_relationships` context or flag exists;
   - `runner-config-v57` is absent from `SUPPORTED_RUNNER_SCHEMA_VERSIONS` and
     from every credit module;
   - `ALEMBIC_HEAD_REVISION == "0017"` and no `alembic/versions/0018*` exists;
   - `len(COMMAND_RULE_MATRIX) == 43` and `len(get_args(AgentCommand)) == 43`;
   - `len(SEMANTIC_EVENT_TYPES) == 73`;
   - max accepted event schema is 27, codec `v25` is accepted, `v22` is not;
   - `OBSERVER_PROTOCOL_VERSION == "observer-protocol-v1"`;
   - `METRIC_FAMILY_COUNT == 216` and the first-212 baseline digest equals
     `87fd875c1b53e588e19af116ca6c974515a5e8fa4b878901def526c096eb496e`;
   - no write pair was added: reserved pairs remain events 23-26 /
     codecs `v21`-`v24` plus the already-accepted 27/`v25`;
   - no credit module uses `bank`, `loan`, `interest`, `credit_score`,
     `money`, `currency`, `enforceable_debt`, `canonical_credit`, or
     `credit_limit` as a dataclass field or class name; the single
     `CREDIT_FORBIDDEN_FIELD_NAMES` constant is allowed and is itself scanned
     as a frozenset of strings;
   - no credit module defines a global registry, table, or module-level mutable
     store.
2. Create `tests/architecture/test_credit_relationships_boundaries.py` with AST
   import checks:
   - `world.credit_relationships` imports no other first-party package; it may
     import `world.communications` and the standard library only;
   - `agents.cognition.credit_relationships` and
     `credit_relationships_communication` import no `simulation`, `analysis`,
     `experiments`, `persistence`, `api`, or `observer`;
   - `analysis.credit_relationships_*` import no `agents.cognition`,
     `simulation`, `experiments`, `persistence`, `api`, or `observer`;
   - `simulation.credit_relationships_*` import no `analysis`, `experiments`,
     `persistence`, `api`, or `observer`;
   - `experiments.credit_relationships_*` import no `api`, `infrastructure`, or
     concrete persistence;
   - `persistence.credit_relationships_filesystem` imports no `analysis`,
     `api`, or `experiments`;
   - `api.routes.credit_relationships` imports no `analysis`, `experiments`, or
     publisher;
   - Python never imports the Research UI or Godot client.
3. Extend `tests/unit/test_credit_relationships_pins.py`:
   - `CREDIT_RELATIONSHIPS_ROUTE_COUNT == 7`;
   - settings names `credit_relationships_root` and
     `credit_relationships_cursor_key`;
   - snapshot/store/policy/version tokens exact;
   - no Godot path contains `credit_relationships`, `crd_v1`, or
     `credit-relationships`;
   - no `runner-config-v57`, `0018`, `/v2`, or new semantic type.
4. Add a route-method scan: every credit route is `GET`; no `POST`, `PUT`,
   `PATCH`, or `DELETE` exists in `api/routes/credit_relationships.py`.
5. Add a write-pair scan: no credit module references a new event number above
   27 or codec above `v25`.
6. Add a snapshot-schema scan: `credit-relationships-snapshot-v1` and
   `credit-relationships-store-v1` appear only in the snapshot/store/publication
   surfaces, not in `simulation.runner_models`, `simulation.runner`,
   `simulation.persistence`, or `alembic/`.
7. Update any stale pin found by the sweep; if a stale pin is historical, leave
   it and record it in the verification receipt.

### Required Interfaces and Contracts

- 14 contexts / 12 flags / 8 owned / 4 unowned.
- `markets_credit` remains the owned context; `supply_chains` and `organizations`
  remain planning prerequisites, never runtime gates.
- 43 commands, 73 observer semantic types, 216 metric families.
- Replay `EVENT_SCHEMA_REPLAY_V27` / codec `v25` maximum; Alembic `0017`.
- `/v1` and `observer-protocol-v1`.
- Seven GET-only credit routes.
- No new write pair, `/v2` route, migration, or Godot overlay.

### Requirement Evidence

- V4-21 invariant template:
  `tests/architecture/test_emergent_prices_invariants.py:40-120`.
- V4 registry and ownership:
  `src/simulation/v4_architecture.py`, `src/simulation/compatibility.py`.
- Version pins: `.ai-factory/ARCHITECTURE.md` "Current baseline through
  V4-18".
- Anti-patterns: `.ai-factory/ARCHITECTURE.md` "Anti-Patterns".

### Error Handling and Logging

- Test-only. Assertion messages name the violating path or field, never row
  payloads.
- No runtime log changes.

### Tests

- `tests/architecture/test_credit_relationships_invariants.py`
- `tests/architecture/test_credit_relationships_boundaries.py`
- `tests/unit/test_credit_relationships_pins.py`
- `tests/architecture/test_emergent_prices_invariants.py`
- `uv run lint-imports`

### Acceptance Criteria

- Any added V4 context/flag, runner schema, command, event, semantic type, write
  pair, migration, `/v2` route, or Godot overlay fails a test.
- Any credit module that imports world/simulation authority in the wrong
  direction fails a test.
- Any active pin that still says 212 fails a test.
- The first-212 catalog digest remains unchanged.

### Verification

- `uv run pytest tests/architecture/test_credit_relationships_invariants.py tests/architecture/test_credit_relationships_boundaries.py tests/unit/test_credit_relationships_pins.py -q`
- `uv run lint-imports`
- Expected: all pass; 25+ contracts kept, 0 broken.

## Phase Risks and Mitigations

- Risk: a structural test encodes a brittle line number.
  Mitigation: assert symbols, counts, and sets, not source line numbers.
- Risk: import checks miss a transitive import.
  Mitigation: parse the AST of every credit module and fail on forbidden
  top-level package names.
- Risk: a historical count is mistaken for an active pin.
  Mitigation: only current-state tokens (counts, sets, protocol names) are
  asserted; historical prose is left alone.

## Phase Completion Checklist

- Task 20 satisfies its acceptance criteria.
- Architecture and pin suites pass.
- `index.md` checkbox is updated only after verified completion.
