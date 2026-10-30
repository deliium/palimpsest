# Phase 4: Observer Protocol and Scale Contracts

Plan: [index.md](index.md)
Tasks: 9-11
Depends on: Phase 1 (Tasks 1-3), Phase 3 (Tasks 7-8)

## Objective

Make the observer protocol's future evolution and the V4 population-scale
execution model explicit and testable, while keeping `observer-protocol-v1` the
only served protocol and adding no aggregation, no server-side LOD, and no
capacity claim.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `src/observer/version.py` | `OBSERVER_PROTOCOL_VERSION`, `OBSERVER_LAYOUT_SCHEMA_VERSION`, `SEMANTIC_EVENT_TYPES` (73) | Current protocol and closed semantic set. |
| `src/observer/contracts.py` | `_require_protocol`, `ObserverManifest.read_only` | Exact-version and read-only enforcement. |
| `src/observer/__init__.py` | public facade and `__all__` | Where capability exports are added. |
| `src/api/presentation_static.py` | `version_payload` (125-152), return type `dict[str, str \| bool \| None]` | Additive `/version` fields land here. |
| `src/api/routes/version.py` | `get_version` response annotation | Must widen to include a string list. |
| `tests/unit/test_presentation_static.py` | exact key-set assertion (211-218) | Must be extended additively. |
| `tests/unit/test_godot_protocol_mirror.py` | protocol mirror checks | Must still pass unchanged. |
| `src/simulation/randomness.py` | seed-derived RNG and namespaced identity patterns | Reference for deterministic, non-`hash()` partitioning. |
| `tests/benchmarks/conftest.py` | integration fixtures | Unit-marked benchmark files do not use them. |
| `pyproject.toml` | markers (107-113) | `scale` is documented as also marked integration; a unit measurement lane must not misuse it. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/observer/capabilities.py` | create | Closed advertised/reserved capabilities and supported protocols. |
| `src/observer/__init__.py` | modify | Export the capability surface. |
| `src/api/presentation_static.py` | modify | Additive `/version` fields. |
| `src/api/routes/version.py` | modify | Widen the return annotation. |
| `src/simulation/scale.py` | create | Deterministic partition and budget contracts. |
| `src/simulation/__init__.py` | modify | Export the scale surface. |
| `tests/unit/test_observer_capability_manifest.py` | create | Protocol/capability invariants. |
| `tests/unit/test_presentation_static.py` | modify | Extend the expected `/version` key set. |
| `tests/unit/test_godot_protocol_mirror.py` | modify | Replace the V3-only `/version` non-goal lock with a flag-payload prohibition that allows capability metadata. |
| `tests/unit/test_v4_scale_contracts.py` | create | Partition/budget properties. |
| `tests/benchmarks/test_v4_scale_contract.py` | create | Opt-in partition measurement lane. |

## Task 9: Add observer protocol negotiation and capabilities

### Intent

Advertise what the server supports without changing any frame shape. A client
must be able to learn the protocol, layout, and capabilities from `/version`
before opening a stream, and a future v2 can be introduced additively without
silently breaking v1 clients.

### Implementation Steps

1. Create `src/observer/capabilities.py`:
   - `ObserverCapability(StrEnum)` with ten members:
     `STRUCTURED_MANIFEST="structured_manifest"`,
     `REPLAY_CURSORS="replay_cursors"`,
     `AGGREGATE_DEMOGRAPHICS="aggregate_demographics"`,
     `CIVILIZATION_OVERLAYS="civilization_overlays"`,
     `MULTI_SCALE_SUMMARIES="multi_scale_summaries"`,
     `ORGANIZATION_ROWS="organization_rows"`,
     `NETWORK_ROWS="network_rows"`,
     `EPIDEMIC_ROWS="epidemic_rows"`,
     `CONFLICT_ROWS="conflict_rows"`,
     `DISASTER_ROWS="disaster_rows"`.
   - `OBSERVER_CAPABILITIES: Final[tuple[ObserverCapability, ...]]` with the four
     implemented capabilities only (`STRUCTURED_MANIFEST`, `REPLAY_CURSORS`,
     `AGGREGATE_DEMOGRAPHICS`, `CIVILIZATION_OVERLAYS`).
   - `RESERVED_OBSERVER_CAPABILITIES: Final[tuple[ObserverCapability, ...]]` with
     the other six, disjoint from the advertised tuple.
   - `SUPPORTED_OBSERVER_PROTOCOLS: Final[tuple[str, ...]] = (OBSERVER_PROTOCOL_VERSION,)`.
   - `RESERVED_OBSERVER_PROTOCOL_VERSION: Final[str] = "observer-protocol-v2"`.
   - `@dataclass(frozen=True, slots=True) class ObserverCapabilityManifest` with
     `protocol_version: str`, `layout_schema_version: str`,
     `supported_protocols: tuple[str, ...]`, `capabilities: tuple[str, ...]`,
     `reserved_capabilities: tuple[str, ...]`, `read_only: bool = True`; a
     `__post_init__` that rejects an empty supported tuple, a served reserved
     protocol, duplicate capability strings, advertised/reserved overlap, and
     `read_only is not True`.
   - `observer_capability_manifest() -> ObserverCapabilityManifest` returning the
     v1 manifest.
   - `observer_capability_payload() -> dict[str, object]` with JSON-safe values
     (`list[str]` for tuples), keyed `protocol_version`,
     `layout_schema_version`, `supported_protocols`, `capabilities`,
     `reserved_capabilities`, `read_only`.
2. In `src/api/presentation_static.py::version_payload`:
   - Import `observer_capability_manifest` (not the generic payload helper).
   - Build `manifest = observer_capability_manifest()` once and add these typed
     values to the returned dict:
     `supported_observer_protocols=list(manifest.supported_protocols)`,
     `observer_layout_version=manifest.layout_schema_version`,
     `observer_capabilities=list(manifest.capabilities)`,
     `observer_reserved_capabilities=list(manifest.reserved_capabilities)`.
   - Widen the return annotation to
     `dict[str, str | bool | None | list[str]]`.
3. In `src/api/routes/version.py`, widen `get_version`'s annotation to match.
   Do not add a response model; the endpoint remains an open-by-design version
   report.
4. Export the capability surface from `src/observer/__init__.py` and its
   `__all__`.
5. Do not change `SEMANTIC_EVENT_TYPES`, `OBSERVER_PROTOCOL_VERSION`,
   `OBSERVER_LAYOUT_SCHEMA_VERSION`, frame parsing, `ObserverManifest`, or any
   route other than `/version`.
6. Update `tests/unit/test_presentation_static.py` to expect the four new keys
   and their exact values; keep every existing assertion.
7. In `tests/unit/test_godot_protocol_mirror.py`, rename
   `test_version_payload_source_has_no_v3_capability_fields` to
   `test_version_payload_has_no_capability_flag_payloads` and update its
   docstring: the endpoint may advertise protocol/layout/capability metadata,
   but it must never expose capability-flag values or configuration payloads.
   Keep the existing forbidden names (`v3_capability_flags`,
   `generational_population`, `kinship_inheritance`, `multi_polity_migration`,
   `institutional_economy`, `cultural_historical_memory`) and add the twelve V4
   flag names to the forbidden list. Assert the allowed metadata keys are
   present. `docs/research-api.md` is updated in Task 16.
8. Create `tests/unit/test_observer_capability_manifest.py`:
   - Manifest validates; `read_only is True`.
   - Advertised capabilities are exactly the four implemented ones; reserved
     are exactly the six others; the union has ten unique values.
   - `SUPPORTED_OBSERVER_PROTOCOLS == ("observer-protocol-v1",)` and
     `"observer-protocol-v2" not in supported`.
   - Payload values are JSON-serializable with `json.dumps`.
   - `len(SEMANTIC_EVENT_TYPES) == 73` and the tuple is unchanged.
   - A manifest that serves v2, overlaps advertised/reserved, or sets
     `read_only=False` raises `ValueError`.
   - AST check: `observer/capabilities.py` imports no `world`, `simulation`,
     `agents`, `api`, `persistence`, or `infrastructure` module.

### Required Interfaces and Contracts

- `/version` remains unauthenticated and additive.
- v1 remains the only served protocol; v2 is declared reserved but not served.
- No new observer semantic type, frame field, stream envelope, layout, or route.
- `/version` exposes protocol/layout/capability metadata only; it must never
  include capability-flag values or configuration payloads.
- Existing Godot v1 clients must tolerate the new JSON keys (they read named
  fields and ignore unknown keys).

### Requirement Evidence

- Original Request: "Observer Protocol versioning", "Godot is read-only".
- `src/observer/contracts.py` exact-protocol and read-only contracts.
- `docs/research-api.md` API versioning policy: prefer additive changes; use
  `/v2` only when a shape cannot be additive.

### Error Handling and Logging

- Manifest validation raises `ValueError` with stable reason strings.
- `/version` logs only the existing `version_payload_built` metadata; add
  `capability_count` and `supported_protocol_count` as integers. Never log
  credentials or request headers.

### Tests

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_observer_capability_manifest.py tests/unit/test_presentation_static.py tests/unit/test_godot_protocol_mirror.py -q`

### Acceptance Criteria

- `/version` reports protocol, layout, advertised, and reserved capabilities.
- v1 is the only served protocol; 73 semantic types unchanged.
- Existing presentation tests pass with only the deliberate additive key update.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_observer_capability_manifest.py -q`
- Expected result: all tests pass, 0 failures.

## Task 10: Add deterministic scale contracts

### Intent

Define how V4 will partition large agent populations deterministically and how
per-tick budgets are expressed, without wiring partitioning into the engine. The
contract must never depend on Python `hash()`, process state, or iteration order
of unordered inputs.

### Implementation Steps

1. Create `src/simulation/scale.py`:
   - `SCALE_CONTRACT_VERSION: Final[str] = "v4-scale-contract-v1"`.
   - `SCALE_PARTITION_NAMESPACE: Final[str] = "palimpsest-scale-partition-v1"`.
   - `@dataclass(frozen=True, slots=True) class ScaleBudget` with
     `max_population: int`, `max_commands_per_tick: int`,
     `max_observer_rows: int`; `__post_init__` rejects non-int, non-positive, and
     `max_population > 100_000` with stable messages.
   - `stable_partition(agent_ids: Iterable[AgentId], *, partitions: int,
     namespace: str = SCALE_PARTITION_NAMESPACE) -> tuple[tuple[AgentId, ...], ...]`:
     - validate `partitions >= 1` and `<= 4096`;
     - for each id compute `blake2b(f"{namespace}\x00{agent_id.value}".encode(),
       digest_size=8).digest()`, convert with `int.from_bytes(..., "big")`, and
       take modulo `partitions`;
     - preserve the input order inside each partition and return partitions in
       index order;
     - reject duplicate ids with `ValueError("duplicate_agent_id")`;
     - accept any `Iterable`, materialize once, and never mutate the input.
   - `partition_balance(partitions: tuple[tuple[AgentId, ...], ...]) -> float`
     returning `max_size / mean_size` with `0.0` for empty input.
   - `validate_scale_budget(budget: ScaleBudget, population: int) -> None`
     raising `ValueError("scale_budget_exceeded")` when `population >
     budget.max_population`.
   - `scale_contract_payload() -> dict[str, object]` with the contract version,
     namespace, and limits for docs/tests.
2. Do not import `simulation.runner`, `WorldEngine`, `world._*`, or any
   persistence module. The module is pure.
3. Export the scale surface from `src/simulation/__init__.py`.
4. Create `tests/unit/test_v4_scale_contracts.py`:
   - Property (Hypothesis, max 200 examples): generated unique id lists map with
     no loss, no duplication, and every id lands in the same partition index as
     a single-id call.
   - Input order is preserved inside each partition.
   - Reversing the input changes neither membership nor partition index per id.
   - Duplicate ids raise; `partitions=0` and `partitions=4097` raise.
   - 10,000 generated ids across 16 partitions have
     `partition_balance(...) < 1.25` (deterministic ids, not random seeds).
   - The same id in two fresh processes (spawn a subprocess printing the
     partition index) returns the same index; this proves no `hash()`
     dependence.
   - `ScaleBudget` rejects zero, negative, bool values, and 100_001 population.
   - Module import opens no resources and logs nothing.

### Required Interfaces and Contracts

- Partition assignment is a pure function of `(namespace, agent_id)` and the
  partition count.
- The namespace is versioned; changing it changes every assignment and requires
  a contract version bump.
- Budgets are declarative; V4-01 does not enforce them at runtime.
- No wall-clock, randomness, or process-global state.

### Requirement Evidence

- Original Request: "hundreds or potentially thousands of agents" and
  "replay/forking remains deterministic where configured".
- `.ai-factory/RULES.md` axiom 4: explicit seeds, no global RNG in domain code.
- `docs/long-horizon-scalability.md` measured-envelope discipline.

### Error Handling and Logging

- Invalid inputs raise `ValueError` with stable codes; no logging.
- No silent fallback to a different namespace or partition count.

### Tests

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_v4_scale_contracts.py -q`

### Acceptance Criteria

- Partitioning is deterministic, pure, lossless, and order-preserving.
- Budget validation fails closed.
- No engine integration or behavior change.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_v4_scale_contracts.py -q`
- Expected result: all tests pass, 0 failures.

## Task 11: Add the opt-in V4 scale qualification lane

### Intent

Provide a reproducible measurement lane for the partition contract so later
plans can compare implementations, without presenting any number as civilization
capacity. The lane is opt-in and unit-marked; a default run skips it with an
explicit reason.

### Implementation Steps

1. Create `tests/benchmarks/test_v4_scale_contract.py` with
   `pytestmark = pytest.mark.unit` (do not use the `scale` marker, which the
   project defines as also integration).
2. Gate on `PALIMPSEST_V4_SCALE_IDS`: when unset or empty, call
   `pytest.skip("PALIMPSEST_V4_SCALE_IDS unset")`; when set, parse a positive
   integer with a maximum of 100_000 and fail with a clear message on invalid
   input.
3. For the requested size, build deterministic ids
   `AgentId(f"scale-agent-{index:06d}")`, partition with 16 partitions, and
   assert:
   - total membership equals the input size with no duplicates;
   - assignment per id equals the single-id contract result;
   - `hashlib.sha256` over the ordered partition indices is stable across two
     runs in the same process.
4. Log a single `INFO` record `v4_scale_contract_measured` with `id_count`,
   `partition_count`, `elapsed_ms` (rounded), `partition_balance`, and
   `index_digest_prefix` (12 hex characters). Do not log ids or payloads.
5. Write no artifact, no JSON file, and no baseline row. The lane is a
   measurement, not a capacity claim.
6. Document the environment variable in Task 16; until then the skip message is
   the discoverability path.

### Required Interfaces and Contracts

- Default collection must skip exactly one test with the documented reason.
- Required release acceptance must not treat this lane as a gate; it is not
  marked `compose`, `integration`, or `scale`.
- No timing assertion; only correctness and digest stability.

### Requirement Evidence

- Original Request: "hundreds or potentially thousands of agents".
- `docs/long-horizon-scalability.md`: measured claims must name the actual
  workload and must not generalize incomplete lanes.

### Error Handling and Logging

- Invalid env input fails with a message naming the variable and expected range.
- The measurement log contains counts, elapsed time, balance, and a digest
  prefix only.

### Tests

- Default: `uv run --frozen --python 3.12.14 pytest tests/benchmarks/test_v4_scale_contract.py -q`
  → 1 skipped.
- Opt-in: `PALIMPSEST_V4_SCALE_IDS=10000 uv run --frozen --python 3.12.14 pytest tests/benchmarks/test_v4_scale_contract.py -q`
  → 1 passed.

### Acceptance Criteria

- The default lane skips with an explicit reason.
- The opt-in lane passes at 1,000, 5,000, and 10,000 ids.
- No artifact or capacity claim is produced.

### Verification

- `PALIMPSEST_V4_SCALE_IDS=10000 uv run --frozen --python 3.12.14 pytest tests/benchmarks/test_v4_scale_contract.py -q`
- Expected result: 1 passed, 0 failed, 0 skipped.

## Phase Risks and Mitigations

- Risk: adding fields to `/version` breaks an exact-shape client.
  Mitigation: Godot reads named fields; the only Python exact-key test is
  updated deliberately, and Task 12 verifies the client.
- Risk: capability names become a de facto wire contract before v2 exists.
  Mitigation: advertised and reserved sets are disjoint and documented as
  advisory; frames remain v1.
- Risk: partitioning is mistaken for an engine feature.
  Mitigation: the module is unused by the engine, and acceptance requires no
  behavior change.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
