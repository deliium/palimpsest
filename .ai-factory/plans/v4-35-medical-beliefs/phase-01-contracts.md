# Phase 1: Activation and owner state

Plan: [index.md](index.md)
Tasks: 1–2
Depends on: none

## Objective

Enable an explicitly selected, deterministic cognition feature without changing the disease engine or any existing write selection.

## Current-Code Evidence

| Path | Symbols | Why it matters |
|---|---|---|
| `src/simulation/runner_models.py` | `SimulationRunnerConfig`, `RUNNER_SCHEMA_VERSION_V58` | Exact v58 activation and shared feature predicates |
| `src/simulation/runner_serialization.py` | `_encode_runner_document`, `decode_runner_config`, `runner_config_fingerprint`, `cognition_fingerprint` | Exact wire shape and separate configuration/behavior identity |
| `tests/unit/test_runner_config_v56.py`, `tests/architecture/test_v3_baseline_inventory.py` | reject `runner-config-v59` | Former negative ceiling tests must move without dropping older-family guards |
| `src/world/observations.py` | `Observation`, `ObservedSelf`, `VisibleBody`, `ObservedItem` | Owner cue and ordinary local context already exist |
| `src/agents/cognition/replication.py` | owner ledger precedent | Frozen records and positive/negative evidence can coexist |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/simulation/medical_beliefs_config.py` | create | Typed exact policy spec |
| `src/simulation/{runner_models,runner_serialization,compatibility,__init__}.py` | modify | Config acceptance, writer and public facade |
| `src/agents/cognition/medical_beliefs.py` | create | Owner-only rows, bounded evidence and deterministic reducer |
| `tests/unit/test_medical_beliefs_{config,ledger}.py` | create | Wire, validation and policy tests |

## Task 1: Add the opt-in runner contract

### Implementation Steps

1. Add frozen `MedicalBeliefsSpec(policy_id="medical-beliefs.v1")`, accepting exactly this string; the runner field `medical_beliefs` defaults to `None`. Define `RUNNER_SCHEMA_VERSION_V59`.
2. Make v59 exactly the accepted v58 family shape plus mandatory `medical_beliefs: {"policy_id":"medical-beliefs.v1"}`. Keep both v58 branches (with and without instruments); do not widen v58. Reuse v58 shape dispatch for the inherited fields, and include v59 in the validation/encode/decode predicates for features v58 already allows. Ensure reconstruction through `dataclasses.replace`, encode/decode, config fingerprinting, and compatibility diagnostics preserves the spec.
3. Require the typed v58 disease spec and owned `epidemics` with its existing prerequisites. Reject missing/null/extra fields, medical spec on earlier versions, and v59 without a valid spec. Keep gate validation before runtime construction. Leave replay version selection untouched: v58 and v59 disease-active worlds still use event 24/`v22`, including the supported instruments combination.
4. In `cognition_fingerprint`, conditionally include the exact medical policy object only when enabled. Do not insert `null` in older fingerprint documents or alter `scenario_fingerprint`. In the schema predicates, distinguish inherited-family acceptance from v58-exclusive and v59-exclusive keys; do not globally replace `V58`. Sweep `tests/unit` and `tests/architecture` for `runner-config-v59`, supported-set inventory assertions and textual source guards. Move only the unsupported-next-version sentinels to v60 and keep old exact-key and feature-ownership assertions.

### Contracts, errors and logging

No new capability flag or per-agent config field. Activation is run-wide, including eligible mid-run admissions. Use stable reason codes (`medical_beliefs_spec_required`, `medical_beliefs_schema_mismatch`, `medical_beliefs_requires_epidemics`, `medical_beliefs_policy_invalid`); DEBUG for selected mode/version only. No serialized spec, disease values or symptom payloads in logs. Older document encodings stay byte-identical.

### Tests and verification

In `tests/unit/test_medical_beliefs_config.py`, derive configs from the checked-in disease scenario builder, test v59 both instruments branches using the existing disease config tests' valid fixtures, exercise bad versions/flag/spec combinations (including v60), and compare pre-change v58 canonical bytes and cognition fingerprints with their post-change values. Assert v58/v59 twins have equal scenario fingerprints but different config and cognition fingerprints; assert v4/v2 defaults and unchanged disease replay selection. Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_medical_beliefs_config.py tests/unit/test_disease_config.py tests/unit/test_runner_config_v56.py tests/architecture/test_v3_baseline_inventory.py -q`. Accept only exact round trips and fail-closed negatives.

## Task 2: Define owner evidence and belief updates

### Implementation Steps

1. In `medical_beliefs.py`, define frozen `MedicalBeliefLedger`, `MedicalCause`, `MedicalPractice`, and immutable row types for `belief`, `attempt`, `outcome`, `interpretation`, and `transmission`. Use the owner `AgentId`, local entity identity, tick, closed enums, and opaque refs; do not store whole observations, testimony bodies, or profiles. No truth or diagnosis field. Carry a compact prior observation frame (tick, cue presence, local location id, weather enum, boolean living peer in local `visible_bodies`, and boolean visible food in own inventory) and last processed tick. Do not infer eating from inventory. An absent/dead self frame cannot establish a negative sample; a gap resets the association baseline. Weather change requires both values known.
2. Use five independent cause slots: `contact`, `food`, `weather`, `location`, `cultural`. At a consecutive observed absent→present transition only, add 2 support for each matching local association: prior co-presence, prior visible held food, changed visible weather, changed self-location. First sample and gaps establish baseline only. Cultural claims originate as marked `cultural` testimony or as a speculative interpretation of a visible local artifact at onset (presence only, never parse its mark text), gaining 2 support. Entries may coexist and are not normalized. No association rises to a confirmed cause. Start newly evidenced slots at 0, clamp integer scores to `[-8, 8]`, with active ranking of scores ≥2, descending score then the declared enum order.
3. Store practice support separately per `(cause, practice)` with the same bounds. A first accepted testimony root adds 2 to its cause and proposed practice; repeats do not increase either score. A cue disappearing after an attempted practice appends `tentatively_helped` and adds 1 practice support; cue persisting appends `not_obviously_helped` and subtracts 1; missing follow-up appends `unknown` and adds nothing. These are judgments about sequence, not effectiveness, and do not adjust the cause score. Never erase dissenting rows because support is low.
4. Retain at most five cause slots, fifteen practice scores (five causes × three practices), and 128 chronological transition rows total. Evict the oldest sealed logical group (an attempt with its linked outcome and interpretation, or a singleton row); never evict an open attempt, and mark `history_truncated` irreversibly. Keep a separate exact set of at most 128 seen `(cause, practice, declared-root)` tuples; once full, unseen tuples cease to contribute, not evict/recount. Store last attempt tick and the first eligible relay anchor per pair separately, so row eviction cannot reset cooldown or change a root. Define `advance(ledger, observation)` as a pure candidate update; repeat tick is a no-op, rewind/wrong owner fails closed. In tick order close prior attempt, apply direct associations, then fold delivered frames in occurrence-reference order. Sort storage by tick, lane order and stable ID.
5. Treat testimony capacity separately from historical row retention. After the 128-root cap, a valid unseen delivery may retain a `capacity_ignored` receipt but cannot create a relay anchor or update scores; known-root deliveries retain `repeat` status. Preserve the latest known (non-`unknown`) outlook per pair in bounded summary state; neither row eviction nor a later missing follow-up rewrites it. Relay and cooldown consult those summaries, not the retained rows. Expose cap exhaustion separately from history truncation so capture cannot imply all valid roots were evaluated.

### Contracts, errors and logging

Validate types, unique IDs, ownership, chronological dependencies and bounded references at construction/restore. Derive IDs by namespaced digest of canonical owner/tick/kind and row identity (not `hash()` or wall clock); attempts are unique per owner/tick, and outcome and interpretation reference the exact attempt. Keep external transmission roots explicitly speaker-declared. Emit DEBUG aggregate counts and bounded reason codes at the calling seam only; no code-level logging of row contents.

### Tests and verification

In `tests/unit/test_medical_beliefs_ledger.py`, cover each association and contradictory/competing causes, first/duplicate/skipped observations, unavailable evidence, wrong owner, temporal links, repeated roots, clamp, deterministic overflow, negative outlook surviving eviction and unknown follow-up, and no relay/support from a capacity-blocked root. Include a property test for deterministic ordering under shuffled equivalent inputs. Run `uv run --frozen --python 3.12.14 pytest tests/unit/test_medical_beliefs_ledger.py -q`. Accept independent owner projections and equal outputs for equal observations even when hidden world state differs.

## Phase Risks and Mitigations

- A new config version can silently change inherited feature validation: compare paired v58/v59 configs differing only by the added field and schema identifier.
- Association could be mistaken for ground truth: use closed subjective labels and make missing context produce no support.

## Phase Completion Checklist

- Contracts, activation matrix and reducer tests pass.
- Update only the verified tasks in `index.md`.
