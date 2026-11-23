<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-36 Ecological Resources

Mode: ultra  
Branch: `main` (existing; no branch created)  
Created: 2026-11-23

## Original Request
v4-36 ecology

Naming requirement:

Use `v4-36-ecological-resources`.

Extend environment with simplified ecological/resource dynamics.

Support:

- renewable resource stocks
    
- regeneration
    
- carrying-like limits
    
- seasonal variation
    
- degradation
    

Keep it intentionally bounded.

The project is not becoming a full ecology simulator.

Primary purpose:

society affects environment  
→ environment affects future society

## Settings

- Testing: yes
- Logging: verbose (safe bounded metadata only)
- Docs: yes

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations"  
Rationale: M8 explicitly reserves ecology ownership and a replay pair; `disasters` remains separate.

## Requirements Reconciliation

Authority: no explicit priority declared. The Original Request defines the feature scope; project rules and executable version/authority contracts constrain how it lands. The roadmap identifies work but does not define stock mechanics. `docs/v4-architecture.md` explicitly excludes an automatic carrying-capacity policy; the requested carrying-like limit is an explicit local stock ceiling, never a population ceiling, planner, or quota.

| Decision / supported combination | Source path and section | Verification evidence |
|---|---|---|
| Renewable stock, seasonal regrowth and withdrawal-induced degradation use existing stock, with one local effective ceiling and passive rest recovery. The next agent action sees actual local quantity through ordinary perception. | Original Request; `docs/v4-architecture.md` → `ecological_feedback`; `src/world/_physical.py` → regeneration loop | Tasks 3–4 and 8: invariant tests, season and shortage, two admitted withdrawals → persisted damage → changed ordinary probe result versus both rest and identical-withdrawal/no-damage controls. |
| Ecology off: accept and write the existing exact root and selected pair; persist no ecology section or event. Includes legacy environment, travel, instrument and disease combinations. | `.ai-factory/ARCHITECTURE.md` → Versioned Extension Contract; `src/simulation/persistence.py` → pair selector | Tasks 1, 5, 8 and 9: checked-in `bf_baseline_v4.json`, live tick, off-path goldens and established feature replay gates. |
| Ecology active: v60 + complete spec + `supply_chains` + existing `environmental_dynamics`; bootstrap zero damage, then write v25/`v23`; unmanaged nodes retain legacy rules. A missing spec, prerequisite or active flag, or ecology on earlier roots, is rejected. | `src/simulation/v4_architecture.py` → `ECOLOGICAL_FEEDBACK`; `src/simulation/versioning.py` → reserved 25/`v23`; `.ai-factory/ROADMAP.md` → M8 | Tasks 1–6: strict and malformed config cases, exact bootstrap/checkpoint rows and phase-ordered fold. |
| Ecology plus legacy composition: generational roots and objective infrastructure, regional travel, measurement, disease or medical beliefs may coexist wherever their existing prerequisites hold. v60 admits only the present compatible siblings. Ecology owns the pair; active inherited sections remain canonical and medical pending finalization stays unchanged. | `src/simulation/runner_serialization.py` → `_v56_family_root_keys` through `_v59_family_root_keys`; `src/simulation/persistence.py` → v22 union | Tasks 1, 5–6, 9: v60 alone; active generational root; v60 with travel + measurement; and v60 with travel + measurement + disease + medical beliefs. Check invalid medical-without-disease, missing inherited prerequisites, and inactive sections absent. |
| Exact effects reconstruct objective history without the ecology policy; v23 carries the existing seasonal spec for historical observations. Trusted matching ecology policy is required to continue. Raw objective history retains the new event; ordinary observer and agent lanes do not expose capacity records. | `.ai-factory/RULES.md` → Axioms; `.ai-factory/ARCHITECTURE.md` → Objective authority and runtime, Versioned Extension Contract; `src/simulation/replay.py` → `_replay_request`; `docs/v4-migration-sequence.md` | Tasks 5–7: season boundary with no supplied API context, trusted/mismatched continuation, commit-binding copies, durable tail/hash proof, hidden-only page fallback and explicit budget error. No new indexed need or migration. |

## Architecture and Decisions

- Manage at most 128 explicitly configured nodes. The world engine owns a small damage row per managed node; `Resource.quantity` is the only available stock and `maximum_quantity` is the baseline.
- Resolve commands first, derive pressure from actual net debits before autonomous renewal, then apply damage and the existing seasonal rate under the effective capacity. Idle recovery raises capacity, not stock directly. Order and rounding are specified in Phase 2.
- New opt-in `runner-config-v60` and reserved 25/`v23` are selected by channel, not numeric rank. The default v4/v2 and earlier exact shapes remain unchanged. No additional capability slot, command, route, settings, migration, observer type, client, metric family, or experiment catalog entry.
- No population limit, species, food web, spatial ecology, hazards/disasters changes, scripted outcome, climate model, conservation controller, or analytics feedback into live execution. No full subjective or API process restart claim.

## Phase Index

1. [Phase 1: Config and state](phase-01-config-and-state.md) — Tasks 1–2
2. [Phase 2: Physical feedback](phase-02-physical-feedback.md) — Tasks 3–4
3. [Phase 3: Replay and visibility](phase-03-replay-and-visibility.md) — Tasks 5–7
4. [Phase 4: Proof and docs](phase-04-proof-and-docs.md) — Tasks 8–10

## Cross-Phase Dependencies

- Task 2 depends on Task 1 for validated policy, IDs and floor; Task 3 uses those rules and row invariants.
- Task 4 depends on Tasks 2–3 and verifies the physical candidate before serialization. Task 5 installs closed event codecs and verifies in-memory engine commits/folds; neither task waits for Task 6's checkpoint and durable verification.
- Task 6 depends on Task 5 to keep active selection, folds and snapshots consistent; Task 7 depends on Task 5 for the registered detail.
- Task 8 depends on Tasks 4–7 for evidence from real runs and replay. Task 9 verifies the combined work; Task 10 publishes the verified contract.

## Tasks

### Phase 1: Config and state
- [x] Task 1: Claim ecology with an exact v60 policy ([details](phase-01-config-and-state.md#task-1-claim-ecology-with-an-exact-v60-policy))
- [x] Task 2: Bind the engine-owned stock damage channel ([details](phase-01-config-and-state.md#task-2-bind-the-engine-owned-stock-damage-channel)) (depends on 1)

### Phase 2: Physical feedback
- [x] Task 3: Implement the bounded stock transition ([details](phase-02-physical-feedback.md#task-3-implement-the-bounded-stock-transition)) (depends on 2)
- [x] Task 4: Integrate at the post-command regeneration boundary ([details](phase-02-physical-feedback.md#task-4-integrate-at-the-post-command-regeneration-boundary)) (depends on 2, 3)

### Phase 3: Replay and visibility
- [x] Task 5: Register and fold ecology effects ([details](phase-03-replay-and-visibility.md#task-5-register-and-fold-ecology-effects)) (depends on 4)
- [x] Task 6: Round-trip checkpoints and verified continuation ([details](phase-03-replay-and-visibility.md#task-6-round-trip-checkpoints-and-verified-continuation)) (depends on 5)
- [x] Task 7: Keep new internal transitions off presentation surfaces ([details](phase-03-replay-and-visibility.md#task-7-keep-new-internal-transitions-off-presentation-surfaces)) (depends on 5)

### Phase 4: Proof and docs
- [x] Task 8: Demonstrate the feedback loop in matched runs ([details](phase-04-proof-and-docs.md#task-8-demonstrate-the-feedback-loop-in-matched-runs)) (depends on 4, 5, 6, 7)
- [x] Task 9: Run compatibility and qualification gates ([details](phase-04-proof-and-docs.md#task-9-run-compatibility-and-qualification-gates)) (depends on 8)
- [x] Task 10: Document the bounded mechanism and rollout ([details](phase-04-proof-and-docs.md#task-10-document-the-bounded-mechanism-and-rollout)) (depends on 9)

## Commit Plan

- Commit 1 (after Tasks 1–3): `feat(simulation): define bounded ecological resource policy and state` — do not enable live selection before commit 2.
- Commit 2 (after Tasks 4–7): `feat(world): apply and replay local ecological resource feedback`
- Commit 3 (after Tasks 8–10): `test(simulation): verify and document ecological resource feedback`

## Definition of Done

- An identical later command has a measurably different result solely because earlier ordinary actions changed local stock renewal and capacity.
- Seasonal growth, shortage, cap and rest recovery are deterministic; no extra RNG; unmanaged and legacy fixtures remain unchanged.
- Active history folds without the ecology policy and verified continuation with matching policy agrees with live. Report the disposable database lane explicitly.
- Public/observer and flags-off gates pass, exact version pins are documented, and the M8 remainder stays open. No work outside the stated scope is bundled.
