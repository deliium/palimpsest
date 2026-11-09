# Phase 9: Docs and verification

Plan: [index.md](index.md)
Tasks: 26-27
Depends on: Phase 8 / Tasks 23-25

## Objective

Document the infrastructure networks seam via `$aif-docs` and certify required
verification gates without editing the roadmap.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
| --- | --- | --- |
| `docs/v4-architecture.md` | infrastructure_networks; Downstream checklist | Ownership status |
| `docs/configuration.md` / `research-api.md` / `research-ui.md` / `analysis-metrics.md` / `physical-simulation.md` | Cross-links | Surfaces |
| `.ai-factory/ARCHITECTURE.md` / `DESCRIPTION.md` | Baseline pins | Through V4-16 |
| `.ai-factory/ROADMAP.md` | M8 | Do not edit |

## Files to Change

| Path | Action | Required change |
| --- | --- | --- |
| `docs/infrastructure-networks.md` | create | Seam page |
| Related docs + AI Factory ARCHITECTURE/DESCRIPTION | modify | Pins and cross-links |
| `.ai-factory/ROADMAP.md` | **do not modify** | `$aif-roadmap` owns |

## Task 26: Documentation via `$aif-docs`

### Intent
Mandatory docs checkpoint for the owned objective channel.

### Implementation Steps
1. Create `docs/infrastructure-networks.md` covering ownership, locked catalog,
   collective-project + cognition bridge, ROAD anchors, public-good explicit
   sets, well/warning public_goods start gate, lifecycle, effects, write pair
   (23,v21), semantic aliases, metrics 184→188, experiment id, dual-gate
   surfaces, and non-goals.
2. Update configuration, research-api, research-ui, analysis-metrics,
   physical-simulation, v4-architecture.
3. Update `.ai-factory/ARCHITECTURE.md` baseline through V4-16 (metrics 188,
   event 23/codec v21 when selected, six owned flags).
4. Update `.ai-factory/DESCRIPTION.md` V4-16 ownership paragraph.
5. English only; technical terms preserved.

### Required Interfaces and Contracts
- Docs: yes ⇒ mandatory before Done.
- Roadmap untouched.

### Error Handling and Logging
- Cite safe reason codes in docs tables.

### Tests
- Documentation parity suite including new page references.

### Acceptance Criteria
- Docs + AI Factory pins match code; ROADMAP unchanged.

### Verification
- `git status -- .ai-factory/ROADMAP.md` clean for that path; docs parity green.

## Task 27: Required-gate verification certification

### Intent
Truthful certification table for every Settings lane.

### Implementation Steps
1. Execute/attempt: unit/architecture/determinism (+coverage), static,
   Research UI, integration, Compose/browser, Godot (incl. overlays),
   benchmark/scale.
2. Record `passed` / `failed` / `unexecuted` + prerequisite.
3. Withhold full certification unless every required lane passed.
4. Confirm no ROADMAP edit and no secrets in `git status`.
5. Do not commit unless user authorizes.

### Required Interfaces and Contracts
- Flags-off regressions remain green
  (`test_v1_regression_gate`, `test_v2_scientific_invariants`).

### Error Handling and Logging
- Safe failure summaries only.

### Tests / Commands
```
uv run pytest tests/unit/test_infrastructure_*.py \
  tests/architecture/test_infrastructure_boundaries.py \
  tests/architecture/test_v4_architecture_invariants.py -q
uv run pytest tests/unit/test_v1_regression_gate.py \
  tests/unit/test_v2_scientific_invariants.py -q
# plus docs/development.md UI/Godot/Compose/benchmark commands
```

### Acceptance Criteria
- Certification table complete and truthful; roadmap untouched; pins match.

### Verification
- Lane table recorded; ROADMAP clean in git status.

## Phase Risks and Mitigations
- Risk: env-gated lanes unavailable.
  Mitigation: explicit `unexecuted` with prerequisite.

## Phase Completion Checklist
- Tasks 26-27 done; roadmap not edited.
