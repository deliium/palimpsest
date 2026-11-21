# Phase 4: Research UI, executable evidence, and release checks

Plan: [index.md](index.md)  
Tasks: 9–12  
Depends on: Phase 3 / Task 8

## Objective

Make the feature observable in a real experiment, retain legal nulls, and document the attribution and operating limits.

## Current-Code Evidence

| Path | Existing seam |
|---|---|
| `clients/research-ui/src/views/ScientificInstitutionsPanel.svelte`, `clients/research-ui/src/api/scientificInstitutions.ts` | Existing run-scoped read-only sidecar view and credentials. |
| `src/experiments/scientific_institutions_scenario.py`, `src/experiments/catalog.py` | Existing registered feature fixtures and separate off-V1 arms. |
| `src/simulation/runner.py`, `src/experiments/civilization_benchmark_execution.py` | `set_intervention_arbiter` allows controlled commands through normal admission and committed resolution. |
| `tests/integration/test_scientific_institutions_runner.py`, `docs/development.md` | Real run integration and pinned verification commands. |

## Files to Change

| Path | Action | Responsibility |
|---|---|---|
| `clients/research-ui/src/api/scienceDiffusion.ts`, `clients/research-ui/src/views/ScienceDiffusionPanel.svelte`, `clients/research-ui/src/views/ScienceDiffusionPanel.test.ts` | Create | Typed access and evidence-class display. |
| `clients/research-ui/src/research/selection.ts`, `clients/research-ui/src/views/RunOverview.svelte` | Modify | Register `science-diffusion` view. |
| `src/experiments/science_diffusion_scenario.py`, `src/experiments/catalog.py` | Create / modify | Register a versioned, off-V1 experiment, no default production wiring. |
| `tests/unit/test_science_diffusion_scenario.py`, `tests/integration/test_science_diffusion_runner.py` | Create | Fixture compatibility, real admitted carrier proof, noninterference. |
| `docs/science-diffusion.md`, `docs/research-ui.md`, `docs/configuration.md`, `docs/development.md`, `README.md`, `AGENTS.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/ROADMAP.md` | Docs checkpoint | Document current pins, usage, gates and measured limitations; update roadmap milestone with evidence only. |

## Task 9: Build the read-only Science diffusion view

1. Implement summary and section wrappers using the existing authenticated request helper; pass credential through headers only, never URLs or link state. Add `science-diffusion` selection and navigation, parse/validate typed responses, and render “Coverage,” “Versions,” “Transmission,” “Changes,” and “Knowledge genealogy.” Mark objective carrier events, owner-scoped uptake, and analytical joins distinctly. Highlight migration/context separately from uptake; labels distinguish confirmed, partial, ambiguous and unavailable. No inferred reconstruction in browser.
2. Pin all section requests to the chosen publication and verify response publication/digest against summary before displaying rows. Reset cursor on run/publication change and abort/ignore stale requests. A zero-row page is “complete-empty” only when its relevant coverage rows establish completeness; otherwise use the covered/partial/unavailable status. Cursor expiration offers reload of the same publication, not switching to latest. No write action or Godot overlay.

### Tests and acceptance

Vitest: credentials in headers, all epistemic labels, stale run/publication reply ignored, nonduplicate pagination, expiration and partial vs zero. Browser logging never prints requests containing credentials or evidence payloads.

**Verification:** `pnpm --dir clients/research-ui test` and `pnpm --dir clients/research-ui check` and `pnpm --dir clients/research-ui build`.

## Task 10: Prove the mechanism with an off-gate experiment

1. Add `catalog.experiment_science_diffusion` following `experiment_scientific_institutions`, returning an `ExperimentDefinition` with ID `science_diffusion@1`, 128-tick horizon, and two paired v56 arms built from the existing V4-32 combined v56 config: `diffusion-science` and `diffusion-science-off` (only the owned science flag differs). No central registration or CLI change. Use pinned deterministic providers/seeds. Enable deterministic `ArtifactInterpretationMode` and V3 written-record and teaching knowledge using the `experiment_ap_knowledge_genealogy` exemplar, without invoking the v35-only profile on v56. Validate both arms through exact codec and `SimulationRunner.from_config`. V57 companion alone carries the instrument spec.
2. Run distinct controlled and unassisted lanes. `CommandOverrideArbiter.maybe_replace` is synchronous: have the integration driver prepare a fixed qualified marker from detached evidence before arming the finite override; do not read a live engine or run analysis inside the arbiter. Use normally admitted native `hyp_v1` + actual teaching relation for the science adoption path, and `sdf_v1` for an addressed model reference followed by a qualified recipient's ordinary durable `Inscribe` relay. Verify committed `ActionResolution` and events plus finalized receiver `HypothesisRevision`/`DeclarativeAdvice`/`ArtifactInterpretation` and V3 entries. Do not inject owner rows in this fixture. Keep observation, interpretation and acquisition ordered by their real phase; same-tick rows count only with matching exact refs. Declare scheduled co-presence and interventions as controlled conditions.
3. Add integration with the real `experiment_ay_regional_migration` configuration composed with science and show a retained source at journey departure/arrival, actual qualification, then later delivery. Use a real v57 measurement run to verify replay pair and capture parity. Add positive composed context tests using actual V4-32 context inputs and actual macro-society window detector/identity assignment on controlled committed-event and owner-boundary fixtures; assert the org service is exact-instance and the cross-society evidence predates delivery. For translation, exercise the existing symbolic interpreter's real message-ID application path and join the captured application, then test an ambiguous constituent. Use detached detector vectors for rare authored transitions (e.g. positive independent rediscovery); distinguish these from achieved unassisted outcomes. Do not require spontaneous uptake, stable institutions, or cross-society ties in the unassisted lane.
4. `tests/integration/test_science_diffusion_runner.py`: round trip capture → detection → actual filesystem publish → ASGI summary and section read; assert a real durable-carrier link to a V3 node, addressed hypothesis uptake, and a model reference observed without copied model state. Compare started-from-same-config capture-off/on event and subjectivity projections and deterministic twin sidecars. Science-off produces no evidence, no false zero uptake metric and no publication.

### Errors, tests, and acceptance

Reject unsupported scenario composition with a closed reason. Record controlled nonadmission separately from unassisted zero and missing evidence; log only safe status and counts. Make fixture failures actionable without emitting raw claims or record content.

**Verification:** `uv run --frozen --python 3.12.14 pytest tests/unit/test_science_diffusion_scenario.py -q` and `uv run --frozen --python 3.12.14 pytest -m integration tests/integration/test_science_diffusion_runner.py -q`. Real admission and round-trip evidence are required; analytical classification coverage does not count as autonomous observation.

## Task 11: Verify authority, compatibility and deterministic behavior

1. Extend `tests/architecture/test_science_diffusion_boundaries.py`: experiment-only producer, no live runtime dependency of analysis, no API imports of experiments/analysis, no artifacts flowing into cognition/observer, no domain or migration schema deltas. Assert current V4 baseline: 17 contexts, 12 flags (9 owned), 45 commands, 73 observer semantics, 275 metrics, runner/result v4/v2 default, v57 opt-in, current replay pairs unchanged, Alembic `0017`, `/v1`, `observer-protocol-v1`.
2. Run focused and full default suites with coverage, V1 and V2 compatibility gates, V4 architecture checks, static and UI tools. Keep older metric-family tests on absolute catalog indices, not trailing slices after appending. Record commands, exact outcomes and missing prerequisites; no capacity, durability, Compose/browser or Godot certification beyond gates actually exercised. No public feature enablement or migration is required; rollback disables the paired reader settings and stops selecting experimental capture without touching runs or deleting artifacts.

### Errors, tests, and acceptance

Fail on unsupported leakage or off-path trajectory differences; identify failed lanes with safe IDs. Existing versions, defaults, and scientific invariants remain unchanged.

**Verification:** `uv run --frozen --python 3.12.14 pytest`; `uv run --frozen --python 3.12.14 ruff check src tests`; `uv run --frozen --python 3.12.14 mypy src tests`; `uv run --frozen --python 3.12.14 lint-imports`. Re-run `tests/unit/test_v1_regression_gate.py`, `tests/unit/test_v2_scientific_invariants.py`, and `tests/architecture/test_v4_architecture_invariants.py` explicitly if separate receipts are needed.

## Task 12: Complete the docs checkpoint

1. Route changes through `$aif-docs`. Document semantics per lane and transformation, exact vs inferred V3 links, relay vs uptake, model reference vs local derivation, non-backdating, disabled/empty/partial, settings/auth and a minimal programmatic capture/publish example. Include one controlled round-trip example with no real payload values and report which channels the unassisted lane actually observed. Make explicit that the absence of evidence is not forgetting or independence.
2. Update the README/agent documentation indexes, current architecture and description pins, and M8 entry once results are known; preserve historical numbers. No new release claim, capacity guarantee, API major or flag ownership. Record unexecuted lanes without conflating them with failures or passing tests.

### Errors, tests, and acceptance

Fail review on broken links, payload examples, legacy pin rewrites, or a docs claim unsupported by the verification receipt. Requirements: configured mandatory documentation checkpoint and architecture versioning rules.

**Verification:** Manually check the linked `docs/science-diffusion.md` from README and AGENTS; compare every advertised field/status/version to the codec/routes and the real integration receipt; repeat the Task 11 suite after pin assertions change.

## Phase Risks and Mitigations

- Exact science provenance cannot be guaranteed in free runs. Report what was observed and use separate controlled mechanism proof.
- Gates that depend on external infrastructure may be unexecuted; report that explicitly rather than certifying them.

## Phase Completion Checklist

- UI, real-run integration, regression and docs evidence recorded; update progress only in `index.md`.
