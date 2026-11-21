# Phase 1: Freeze qualified science evidence

Plan: [index.md](index.md)  
Tasks: 1–2  
Depends on: none

## Objective

Produce bounded, chronology-preserving inputs from actual finalized runs without changing how agents act, learn, or persist.

## Current-Code Evidence

| Path | Existing seam |
|---|---|
| `src/simulation/runner.py`, `src/simulation/fork_checkpoint.py`, `src/simulation/run_control.py` | `export_finalized_research_boundary`, `FinalizedResearchBoundary`, `AgentRuntimeCheckpoint` expose run/config, owner/body bindings, science, interpretation, translation and advice state after finalization. |
| `src/simulation/engine.py`, `src/simulation/observer_facts.py` | `detached_objective_facts` / `ObjectiveFacts.artifacts` expose exact physical content revisions; `ArtifactCreated`/`ArtifactModified` do not carry artifact content. |
| `src/experiments/scientific_institutions_capture.py` | `run_with_scientific_institution_capture` is the existing explicit run wrapper; do not reuse its 32-tick sampling for short-lived owner rows. |
| `src/agents/cognition/experimentation.py`, `src/agents/cognition/scientific_models.py` | `experiment_hypothesis_id`, `HypothesisRevision`, `PredictiveModel`, `ModelRevision`: owner-local identity and versioned content are separate. |

## Files to Change

| Path | Action | Responsibility |
|---|---|---|
| `src/analysis/science_diffusion_contract.py` | Create | Frozen input rows, enums, bounds and qualified keys. |
| `src/experiments/science_diffusion_capture.py` | Create | Explicit finalized run wrapper and bounded, incremental capture. |
| `src/experiments/science_diffusion_projection.py` | Create | Owner, science version and exact provenance projection; no public raw content. |
| `tests/unit/test_science_diffusion_contract.py`, `tests/unit/test_science_diffusion_capture.py` | Create | Contract/cap/finalization and noninterference tests. |

## Task 1: Define qualified evidence and version keys

### Intent and implementation

1. Define frozen `DiffusionInputs`, `ScienceVersion`, `DiffusionOccurrence`, `LaneCoverage`, and `EvidenceRef`. Keep objective occurrences, owner evidence, and derived output distinct. Closed lanes: `science`, `speech`, `teaching`, `records`, `knowledge_genealogy`, `organizations`, `migration`, `societies`, `translation`; states: `complete`, `partial`, `unavailable`. Represent complete-empty as `complete` with zero rows. Join flags and unresolved reasons are not availability states.
2. Qualify science versions by `(run_id, owner_id, kind, local_id, revision_index)` with a separate immutable first-observed boundary. Preserve real event ID plus `(tick, sequence)`, owner/body bindings, artifact instance plus content revision, and knowledge entry keys `(run_id, owner_id, entry_id)`. No cross-run references. Reject duplicate qualified keys with inconsistent immutable values.
3. Define canonical SHA-256, domain-separated, sorted-key compact UTF-8 JSON fingerprints. Hypotheses have explicit comparable fields `operator`, ordered operand refs, `process`, `predicted_outcome`, normalized typed conditions; retain missing fields as unknown, never wildcard. Keep native wire projection distinct from the full descriptor. Models compare target kind/ref, unit, horizon, variant, condition set, predicted class, and retained parameter digest. Use kinds and normalized typed refs as specified by the sources; do not substitute generic aliases for a concrete ref. Exclude owner, revision index, clocks, confidence, support, and local evidence IDs from content comparisons. Non-portable model parameter digests compare only when their descriptor scopes are equal. Exact equality is representational, not scientific equivalence.
4. Use tick intervals `[start,end)`, with boundary `b` exposing commits `<b`. Separate occurrence time, first observation, and confirmation time. A later snapshot must not make an assertion available earlier. For no-sequence owner events require strictly earlier ticks unless an exact causal evidence ref proves same-tick source ordering. Project caps: 512 committed ticks, 128 registered owners, 32,768 cumulative committed events, and 16,384 normalized input rows across all retained lanes. Preflight registrations/event count before checkpoint export; stage each boundary's normalized additions before updating state. On aggregate overflow discard the whole staged boundary and seal the trusted prefix with a bounded coverage tail (reserve one tail per lane outside the evidence-row budget). Never silently keep a biased partial batch.

### Errors, tests, and acceptance

Use closed reason codes (`identity_conflict`, `unsupported_schema`, `coverage_gap`, `limit_reached`, `source_not_prior`, `malformed_evidence`). Reject structural violations; filters report hostile or missing in-band evidence as unresolved. Log only lane names, counts, outcome codes and operational run IDs; never log tokens representing claims or digests. Add tests for unknown keys/enums, ordered operands, unknown vs absent fields, same-tick rules, duplicate or foreign refs, deterministic permutations, and confidence-only changes. Requirements: original request; architecture §§ “Key Principles” and “Versioned Extension Contract”.

**Verification:** `uv run --frozen --python 3.12.14 pytest tests/unit/test_science_diffusion_contract.py -q`. Passes with independent lane availability and no content leakage from validation errors.

## Task 2: Capture finalized boundaries and project V4 sources

1. Add `run_with_science_diffusion_capture(runner, *, capture: bool = False)`. Disabled or unsupported (core gates `science` + `predictive_world_model` + `bounded_experimentation` not met, configured horizon over cap, or runner already advanced before attachment) delegates to normal execution and returns `unavailable`; optional carrier/context gates never gate core capture. Sample boundary zero and each nonterminal `RunnerAttemptStatus.FINALIZED` receipt exactly once. Mirror `SimulationRunner.run` for stop/maximum/abort semantics without inventing recovery or retry behavior. On normal stop call `finish_run` exactly once, then sample terminal boundary only if its receipt is finalized and its cursor is not yet sampled: `_detached_boundary_inputs(allow_terminal=True)` rejects terminal receipts before `finish_run`. No terminal sample/publication on abort or unresolved finalization. Preserve normal runner exceptions; catch export/projection failures only at the capture boundary.
2. Take matching public `ObjectiveFacts` and `FinalizedResearchBoundary` from the idle runner. Validate run/config, tick/revision and unique matching registrations (existing owner/body bindings immutable; new owners may appear). Hash the canonical committed event prefix, including baseline events: duplicate or changed earlier occurrence, cursor mismatch, or non-adjacent captured boundary closes the trusted prefix; never infer across or resume a broken prefix. Missing/evicted owner history marks only the affected lanes partial; occurrence counts from the still-valid objective stream remain usable. Export/backend error stops the sidecar and preserves scientific execution (`failed`, no publication); cap deliberately seals a partial prefix eligible for publication after successful finish. Normalize immediately; retain no full checkpoint or event stream across boundaries. For reading at cognition tick `t`, require the exact physical artifact revision in inventory at boundary `t`; a revision created and overwritten between captures is unobservable, not a reconstructible payload. Retain a dead owner's last proven row only as historical evidence; death neither retires a claim nor proves forgetting.
3. Project each first-seen `HypothesisRevision` with declared `evidence_ref`, `source_kind`, and revision number. Project each model revision, model hypothesis source refs and linked frozen prediction/result refs from `ScientificModelLedger`; link production models only through exact owner-local hypothesis refs. Ground positive roots in committed deliberate `ExperimentResolved` or in retained exact observation/source references where observation identity is reconstructible; a generic `observation` marker is not a root. Follow `_execution_facts` in `src/experiments/scientific_institutions_completed_run.py` for objective facts, not for authority. Unavailable translations, artifacts, genealogy, or organizations affect only their lanes.

### Errors, tests, and acceptance

On abort do not publish. On capture error emit one reason-code warning; if only a bounded lane is incomplete, mark affected intervals and retain previously proven rows. Tests: real capture-on/off twins with identical config/runner result/events, terminal receipt before/after finish, off path with zero capture exports, injected sampler failure, prefix mutation, transient dropped history, death, retry/no double harvest, cap atomicity, and mismatch of tick-start artifact revision. Requirements: architecture §§ “Objective authority and runtime”, “Important V3 seams”, and V4-32 precedent.

**Verification:** `uv run --frozen --python 3.12.14 pytest tests/unit/test_science_diffusion_capture.py tests/unit/test_science_diffusion_contract.py -q`. Identical scientific execution, strict capture identity and no post-abort publication.

## Phase Risks and Mitigations

- Prefix export is potentially quadratic; cap the experimental envelope, compare incrementally at the projection boundary, and make no scale claim.
- Checkpoint state is privileged. Only the experiment bridge may materialize it; `analysis` receives detached typed rows and no live service.

## Phase Completion Checklist

- Both task verifications pass; update progress only in `index.md`.
