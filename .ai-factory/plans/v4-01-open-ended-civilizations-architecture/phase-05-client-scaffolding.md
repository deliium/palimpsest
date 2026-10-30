# Phase 5: Client Scaffolding

Plan: [index.md](index.md)
Tasks: 12-13
Depends on: Phase 4 (Task 9)

## Objective

Teach both read-only clients to consume the additive version/capability contract
and to express the multi-scale vocabulary, without adding a view that writes,
without a server-side aggregation contract, and without changing any protocol
frame.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|------|-----------------|----------------|
| `clients/godot-observer/scripts/protocol/models.gd` | `PROTOCOL_VERSION` (6), `LAYOUT_SCHEMA_VERSION` (7), `_protocol_matches` (503) | Exact-equality protocol check to turn into membership without accepting v2. |
| `clients/godot-observer/scripts/net/version_client.gd` | `local_lines` (10), `lines_from_body` (25) | `/version` parsing; ignores unknown keys today. |
| `clients/godot-observer/scripts/ui/status_bar.gd` | `show_versions` (29), calls at 102/144/154, `unsupported_observer_protocol` (60-61) | Version display and mismatch reason. |
| `clients/godot-observer/scripts/presentation/scale.gd` | `ObserverScale.pixels_per_unit` | Presentation scale helper where the level vocabulary belongs. |
| `clients/godot-observer/tests/run_protocol.gd` | 47-suite registry | New suites must be registered. |
| `clients/research-ui/src/api/client.ts` | `apiFetchResponse` and auth handling | Where the public `/version` fetch belongs. |
| `clients/research-ui/src/api/researchSchemas.ts` | handwritten guards | Pattern for a strict version payload parser. |
| `clients/research-ui/src/App.svelte` | header/chrome composition | Mount point for a read-only protocol badge. |

## Files to Change

| Path | Action | Required change |
|------|--------|-----------------|
| `src/observer/scale.py` | create | Presentation scale levels and row caps. |
| `src/observer/__init__.py` | modify | Export the scale surface. |
| `clients/godot-observer/scripts/protocol/models.gd` | modify | Supported-protocol membership; reserved constant. |
| `clients/godot-observer/scripts/net/version_client.gd` | modify | Parse supported protocols and capabilities. |
| `clients/godot-observer/scripts/ui/status_bar.gd` | modify | Display protocol/capability summary safely. |
| `clients/godot-observer/scripts/presentation/scale.gd` | modify | Multi-scale level constants and selection. |
| `clients/godot-observer/tests/test_multiscale_presentation.gd` | create | Level and negotiation tests. |
| `clients/godot-observer/tests/run_protocol.gd` | modify | Register the new suite. |
| `tests/unit/test_observer_scale_mirror.py` | create | Python/GDScript level parity. |
| `clients/research-ui/src/api/versionSchema.ts` | create | Strict `/version` parser. |
| `clients/research-ui/src/api/client.ts` | modify | `getVersion()` using the parser. |
| `clients/research-ui/src/components/research/ProtocolBadge.svelte` | create | Read-only protocol/capability display. |
| `clients/research-ui/src/components/Shell.svelte` | modify | Mount the badge in the existing header/chrome (`App.svelte` delegates to `Shell.svelte`). |
| `clients/research-ui/src/api/versionSchema.test.ts` | create | Parser acceptance/rejection tests. |
| `clients/research-ui/src/components/research/ProtocolBadge.test.ts` | create | Rendering and unavailable-state tests. |

## Task 12: Add Godot multi-scale and protocol scaffolding

### Intent

Give the observer a shared, versioned vocabulary for presentation scale and let
it report the server's advertised protocol/capabilities. The client remains a
read-only consumer of `observer-protocol-v1` frames.

### Implementation Steps

1. Create `src/observer/scale.py`:
   - `OBSERVER_SCALE_CONTRACT_VERSION: Final[str] = "observer-scale-v1"`.
   - `ObserverScaleLevel(StrEnum)` with `AGENT`, `COHORT`, `SETTLEMENT`,
     `REGION`, `CIVILIZATION` and values equal to their lowercase names.
   - `ObserverScaleProfile` frozen slots dataclass: `level`,
     `population_floor: int`, `population_ceiling: int | None`,
     `max_rows: int`, `label: str`.
   - `OBSERVER_SCALE_PROFILES` with these exact thresholds:
     agent `< 24` / 500 rows, cohort `24..199` / 250 rows, settlement
     `200..1_999` / 200 rows, region `2_000..19_999` / 150 rows,
     civilization `>= 20_000` / 100 rows.
   - `select_scale_level(population: int) -> ObserverScaleLevel` rejecting
     negative input.
   - `scale_profile_for(level: ObserverScaleLevel) -> ObserverScaleProfile`.
   - `scale_contract_payload() -> dict[str, object]`.
2. Export the scale surface from `src/observer/__init__.py`.
3. In `clients/godot-observer/scripts/protocol/models.gd`:
   - Add `const SUPPORTED_PROTOCOLS: Array[String] = [PROTOCOL_VERSION]`.
   - Add `const RESERVED_PROTOCOL_VERSION := "observer-protocol-v2"`.
   - Keep the existing `_protocol_matches(data: Dictionary) -> bool` signature.
     Change its final comparison to
     `return SUPPORTED_PROTOCOLS.has(str(data["protocol_version"]))` and keep
     the null/missing guard. Do not add v2 to the array.
4. In `clients/godot-observer/scripts/net/version_client.gd`:
   - `lines_from_body` additionally reads
     `supported_observer_protocols` (array of strings; default
     `[Protocol.PROTOCOL_VERSION]`), `observer_capabilities` (array of strings;
     default empty), `observer_reserved_capabilities` (array of strings; default
     empty), and `observer_layout_version` (string; default
     `Protocol.LAYOUT_SCHEMA_VERSION`).
   - Return the four new keys for every successful parse. Keep `ok=false` on
     non-dictionary bodies.
5. In `clients/godot-observer/scripts/ui/status_bar.gd`:
   - Extend `show_versions` with optional parameters
     `capability_count: int = 0`, `reserved_count: int = 0`,
     `supported_count: int = 1`.
   - Append one line `capabilities N (+M reserved), protocols K` only when
     `loaded` is true and at least one of the counts is non-zero. Keep the
     existing four-line output otherwise.
   - Update the three internal call sites to pass the parsed counts.
   - Keep `show_state("unsupported_observer_protocol", ...)` text unchanged.
6. In `clients/godot-observer/scripts/presentation/scale.gd`:
   - Add `const SCALE_CONTRACT_VERSION := "observer-scale-v1"`,
     `const SCALE_LEVELS: Array[String] = ["agent", "cohort", "settlement",
     "region", "civilization"]`, and the same five thresholds as
     `src/observer/scale.py`.
   - Add `static func level_for_population(population: int) -> String` returning
     the matching level and clamping negatives to `"agent"`.
   - Do not change `pixels_per_unit`, camera limits, or LOD thresholds in
     `scripts/protocol/playback.gd`.
7. Create `clients/godot-observer/tests/test_multiscale_presentation.gd`:
   - Levels match thresholds at 0, 23, 24, 199, 200, 1_999, 2_000, 19_999,
     20_000.
   - `SUPPORTED_PROTOCOLS` contains v1 and not v2;
     `_protocol_matches({"protocol_version": "observer-protocol-v1"})` is true
     and `_protocol_matches({"protocol_version": "observer-protocol-v2"})` is
     false.
   - `VersionClient.lines_from_body` with a payload containing the additive
     fields returns the parsed arrays; with a payload missing them returns v1
     defaults.
   - `show_versions` with counts produces the extra line; without counts it
     produces the legacy output. Use a headless `PanelContainer` instance or
     assert against `status_text()` through the existing test double pattern
     used by other UI tests.
8. Register the new suite in `clients/godot-observer/tests/run_protocol.gd`
   following the existing alphabetical/grouped ordering; the registry count
   becomes 48.
9. Create `tests/unit/test_observer_scale_mirror.py` that parses both
   `src/observer/scale.py` and `clients/godot-observer/scripts/presentation/scale.gd`
   and asserts identical level names and thresholds, plus the 20,000 boundary.

### Required Interfaces and Contracts

- Godot accepts only `observer-protocol-v1`; the reserved v2 constant is not
  served and not accepted.
- No frame parsing change, no new signal, no new panel, no write call.
- Scale levels are presentation-only and never sent to the server.
- The Python and GDScript contracts are byte-for-byte comparable through the
  parity test.

### Requirement Evidence

- Original Request: "multi-scale Godot visualization", "Godot is read-only",
  "Observer Protocol versioning".
- `docs/observer.md` read-only authority split.

### Error Handling and Logging

- Unknown capability arrays log `version_capabilities_unknown` at INFO with
  counts only.
- A protocol mismatch continues to surface `unsupported_observer_protocol` and
  must not attempt a downgrade.
- No payload, run id, or credential logging.

### Tests

- `python -c` mirror test through pytest:
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_observer_scale_mirror.py -q`
- Godot:
  `"${GODOT_BIN}" --headless --path clients/godot-observer --script res://tests/run_protocol.gd`
- Expected: 48 suites, 0 failed.

### Acceptance Criteria

- The client parses additive `/version` fields and remains v1-only.
- Scale threshold parity passes.
- The protocol registry reports 48 suites with zero failures.

### Verification

- `uv run --frozen --python 3.12.14 pytest tests/unit/test_observer_scale_mirror.py -q`
- `"${GODOT_BIN}" --headless --path clients/godot-observer --script res://tests/run_protocol.gd`
- Expected: pytest passes; Godot prints `godot_protocol_tests failed=0`.

## Task 13: Add Research UI version and capability scaffolding

### Intent

Let the researcher SPA display the protocol and capability summary from the same
additive `/version` contract, with a strict parser that rejects malformed
payloads instead of rendering a misleading green state.

### Implementation Steps

1. Create `clients/research-ui/src/api/versionSchema.ts`:
   - Export `VersionPayload` type with `application_version: string | null`,
     `protocol_version: string`, `supported_observer_protocols: string[]`,
     `observer_layout_version: string`, `observer_capabilities: string[]`,
     `observer_reserved_capabilities: string[]`,
     `export_engine: string | null`, `export_renderer: string | null`,
     `revision: string | null`, `research_ui_configured: boolean`.
   - Export `parseVersionPayload(value: unknown): VersionPayload` using the
     existing guard helpers; reject missing/empty protocol, duplicate protocol
     or capability entries, advertised/reserved overlap, and a supported list
     that does not contain `protocol_version`.
2. In `clients/research-ui/src/api/client.ts`, add
   `getVersion(signal?: AbortSignal): Promise<VersionPayload>`. Because
   `apiFetchResponse` requires a `CapabilitySlot`, do **not** use it for this
   public endpoint; call `fetch('/version', { signal, headers: { Accept:
   'application/json' } })` and validate with `parseVersionPayload`. Do not
   attach a capability header, do not add a new capability slot, and do not
   widen `FetchOptions`.
3. Create `clients/research-ui/src/components/research/ProtocolBadge.svelte`:
   - Props: `version: VersionPayload | null`, `unavailableReason: string | null`.
   - Render `protocol <version>`, `N capabilities`, and `M reserved`; render
     `version unavailable (<reason>)` when null. No links, no actions.
   - Use existing chrome classes from `components/research`; do not add global
     CSS or a new design system.
4. Mount the badge in `Shell.svelte` inside the existing header/chrome region
   (`App.svelte` renders `Shell.svelte`), fetching once on mount and treating
   failure as an unavailable state rather than an error banner.
5. Create `clients/research-ui/src/api/versionSchema.test.ts`:
   - Accepts a complete payload and a payload with empty capability arrays.
   - Rejects a missing protocol, duplicate capability, overlap, and a supported
     list missing the active protocol.
   - Rejects non-boolean `research_ui_configured`.
6. Create `clients/research-ui/src/components/research/ProtocolBadge.test.ts`:
   - Renders protocol and counts.
   - Renders the unavailable reason when `version` is null.
   - Renders nothing actionable (no `button`/`a` elements).

### Required Interfaces and Contracts

- `/version` remains unauthenticated; no capability credential is sent.
- The SPA remains read-only: no POST/PUT/PATCH/DELETE.
- Unknown future capability names are displayed as counts, not interpreted.
- Failure to parse is an explicit unavailable state, never a zero/complete claim.

### Requirement Evidence

- Original Request: "researcher analytics are not automatically agent
  knowledge" and the V1-V3 read-only UI invariant.
- `clients/research-ui/src/api/researchSchemas.ts` existing strict-guard pattern.

### Error Handling and Logging

- Browser console logging is limited to a safe reason code
  (`version_payload_invalid`); never log the payload.
- No retry loop and no polling; one fetch per mount.

### Tests

- `cd clients/research-ui && pnpm test`
- `cd clients/research-ui && pnpm check`
- `cd clients/research-ui && pnpm build`

### Acceptance Criteria

- Parser and badge tests pass.
- `check` reports 0 errors and 0 warnings.
- Build succeeds without host-level changes.

### Verification

- `cd clients/research-ui && pnpm test && pnpm check && pnpm build`
- Expected: all tests pass; 0 errors/warnings; build exit 0.

## Phase Risks and Mitigations

- Risk: the Godot client starts accepting v2 before the server serves it.
  Mitigation: membership is restricted to the single-element supported array,
  and the reserved constant is asserted not to match.
- Risk: Research UI duplicates the server capability vocabulary.
  Mitigation: the badge displays counts and raw strings only; no local enum of
  capability semantics.
- Risk: UI fetch breaks on older servers.
  Mitigation: the parser treats the additive fields as required because the UI
  and server ship together; a missing field renders unavailable, not green.

## Phase Completion Checklist

- Every Task N in this phase satisfies its acceptance criteria.
- Required verification commands pass.
- `index.md` task checkboxes are updated immediately after verified completion.
