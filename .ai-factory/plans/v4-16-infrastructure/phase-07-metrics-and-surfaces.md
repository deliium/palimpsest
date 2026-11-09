# Phase 7: Metrics and read-only surfaces

Plan: [index.md](index.md)
Tasks: 18-22
Depends on: Phase 6

## Objective

Append four detached metric families (184→188) with an explicit
`MetricComputationInputs` emit gate, then ship dual-gate snapshot/store, API,
Research UI, and Godot overlays.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `src/analysis/specifications.py` | `METRIC_FAMILY_COUNT = 184` | Pin bump |
| `src/analysis/metric_service.py` | `MetricComputationInputs` 225+; emit gates | Optional analysis field |
| Borders/migration settings + routes + UI + Godot | dual-gate precedent | Copy pattern |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `src/analysis/infrastructure_metrics.py` | create | Four builders |
| `src/analysis/specifications.py` | modify | 184→188 |
| `src/analysis/metric_service.py` | modify | Optional input + emit |
| `src/simulation/infrastructure_{models,codec,ports,paging}.py` | create | Snapshot contracts |
| `src/experiments/infrastructure_{completed_run,publication}.py` | create | Publish bridge |
| `src/persistence/infrastructure_filesystem.py` | create | Store |
| `src/infrastructure/settings.py` | modify | Dual-gate settings |
| `src/research_runner/cli.py` | modify | Flags + publish |
| `src/api/routes/infrastructure_networks.py` | create | Six GET routes |
| `src/api/app.py` | modify | Attach + router |
| Research UI + Godot overlay files | create/modify | Panel + overlays |
| Matching tests | create/modify | Coverage |

## Task 18: Four metric families (184→188)

### Intent
Researcher metrics without a civilization infrastructure score.

### Implementation Steps
1. Families: `infrastructure_network_structure@1`,
   `infrastructure_condition_lifecycle@1`,
   `infrastructure_effect_coverage@1`,
   `infrastructure_maintenance_burden@1`.
2. Add optional `MetricComputationInputs.infrastructure_networks_analysis`
   (or harvest rows); absent/empty ⇒ empty value maps (diplomacy/ISR pattern).
3. Value keys: counts, availability, quantized ratios; forbid score fields.
4. Raise catalog 184→188; append `_BUILDERS`; sweep **current** pins only.

### Required Interfaces and Contracts
- First 184 keep id/order/version/value keys.
- Analysis isolation: no cognition import.

### Error Handling and Logging
- DEBUG emit counts; WARN partial coverage.

### Tests
- Emit gate absent/present; forbid-list; catalog 188.
- `uv run pytest tests/unit/test_infrastructure_metrics.py tests/architecture/test_v3_baseline_inventory.py -q`

### Acceptance Criteria
- Catalog 188; empty when inputs absent; no composite score.

### Verification
- Metrics tests green.

## Task 19: Snapshot, ports, paging, filesystem store

### Intent
Canonical `infrastructure-networks-snapshot-v1` + store-v1.

### Implementation Steps
1. Exact-key codec, 4 MiB / row caps, digests.
2. Separate read vs publication ports; purpose-bound cursors.
3. Atomic FS publish with quotas.
4. Objective asset rows only — no analytical score panel.

### Required Interfaces and Contracts
- Document/store ids as above.

### Error Handling and Logging
- `infrastructure_networks_size_limit`,
  `infrastructure_networks_publication_exists`,
  `infrastructure_networks_store_corrupt`.

### Tests
- Round-trip; size; duplicate; corrupt.
- `uv run pytest tests/unit/test_infrastructure_snapshot.py -q`

### Acceptance Criteria
- Byte-stable snapshot; atomic store; safe errors.

### Verification
- Snapshot tests green.

## Task 20: Settings dual-gate, CLI, publication

### Intent
Attach reader only when root and cursor key (≥32 UTF-8 bytes) are both set.

### Implementation Steps
1. Settings + env `PALIMPSEST_INFRASTRUCTURE_NETWORKS_ROOT` /
   `PALIMPSEST_INFRASTRUCTURE_NETWORKS_CURSOR_KEY`.
2. `bootstrap_fields()` booleans only.
3. CLI flags + post-completion publish; scientific status isolated.
4. Dual-gate attach in `api/app.py`.

### Required Interfaces and Contracts
- Missing either ⇒ 503 `infrastructure_networks_disabled`.

### Error Handling and Logging
- INFO enable/disable; never log cursor key material.

### Tests
- Dual-gate matrix; short key fails; CLI disabled receipt.
- `uv run pytest tests/unit/test_infrastructure_settings.py -q`

### Acceptance Criteria
- Dual-gate enforced; publication non-interfering.

### Verification
- Settings tests green.

## Task 21: API routes and Research UI panel

### Intent
Six SUBJECTIVE_DEBUG GET routes + view `infrastructure-networks`.

### Implementation Steps
1. Routes under `/v1/simulations/{run_id}/infrastructure-networks` (summary,
   assets, edges, condition, effects, maintenance).
2. Cursor bind/mismatch/expiry semantics like borders.
3. Research UI client/panel/allow-list/RunOverview link; no score chrome.

### Required Interfaces and Contracts
- SUBJECTIVE_DEBUG; English UI.

### Error Handling and Logging
- 503/404/400/410/500 mapping as borders.

### Tests
- Route tests + UI vitest/allow-list.
- `uv run pytest tests/unit/test_infrastructure_routes.py -q` plus Research UI
  panel tests.

### Acceptance Criteria
- Six routes + read-only panel; disabled without dual-gate.

### Verification
- API/UI tests green.

## Task 22: Godot infrastructure overlays

### Intent
Presentation-only objective overlays (≤ four kinds).

### Implementation Steps
1. Overlay script for node/edge/damaged/destroyed.
2. Wire into world_view/main like migration/borders.
3. Reject unknown kinds with `reason_code=unknown_kind`.
4. No new observer semantic types; overlays consume objective presentation data.

### Required Interfaces and Contracts
- Protocol `observer-protocol-v1`; semantics remain 73.

### Error Handling and Logging
- `unknown_kind` / `forbidden_field`.

### Tests
- Godot overlay tests; Python semantic pin 73.
- Godot suite per `docs/development.md`.

### Acceptance Criteria
- Overlays render objective state; semantics unchanged.

### Verification
- Godot overlay tests `failed=0` when executed.

## Phase Risks and Mitigations
- Risk: UI invents health score.
  Mitigation: forbid-list on panel props + tests.

## Phase Completion Checklist
- Tasks 18-22 done; catalog 188; surfaces dual-gated.
