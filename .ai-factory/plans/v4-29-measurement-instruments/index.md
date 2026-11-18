<!-- aif:plan-mode:ultra -->
# Ultra Implementation Plan: V4-29 Measurement Instruments

Mode: ultra
Branch: main (existing branch; branch creation disabled)
Created: 2026-11-18
Identifier: `v4-29-measurement-instruments`
Status: implemented; all 24 tasks complete (optional environment-bound lanes unexecuted)
Refined: 2026-11-18 — seven code-grounded refinements approved; task IDs/statuses preserved

## Original Request

v4-29 measurement

Naming requirement:

Use `v4-29-measurement-instruments`.

Introduce physical measurement tools where useful.

Examples:

- temperature-like measurement
    
- resource quantity estimate
    
- duration/time
    
- distance/travel estimate
    
- weight/amount categories
    

Instruments have objective properties such as:

precision  
bias/error  
damage  
calibration state

Agents may misunderstand instrument reliability.

Measurements become observations/evidence, not direct truth.

## Settings

- Testing: yes; focused, property, architecture, regression and real-run tests. Keep coverage enabled.
- Logging: verbose, metadata-only; never display/sample values, calibration parameters, memory/claims, payloads or content-surrogate fingerprints.
- Docs: yes; mandatory `$aif-docs` completion checkpoint.
- Git: enabled; base `main`; no new branch/worktree; no automatic commit/push.
- Language: English artifacts/UI; preserve technical terms.
- Verification: normal; report prerequisite-bound lanes honestly.
- Research: no research artifact exists or influenced this plan.
- Scope: planning only. Implementation starts only on a subsequent explicit request.

## Roadmap Linkage

Milestone: "M8 — V4 Open-Ended Civilizations"
Rationale: Deepen owned science with engine-owned physical instrument actions and owner-scoped, fallible measurement evidence, preserving world/subjective/presentation boundaries.

M8 remains open. The milestone's listed future unowned flags are not an exclusive scope contract and this plan claims none of them. Roadmap changes must be routed through `$aif-roadmap`; this planning invocation does not modify ROADMAP.

## Requirements Reconciliation

Authority: explicit user scope and naming, project axioms/base rules, then current architecture/version contracts. Existing dated landing descriptions are compatibility baselines, not prohibitions on a co-landed versioned extension. No unresolved behavioral source conflict was found.

| Decision / supported combination | Source path and section | Verification evidence |
|---|---|---|
| Physical tools with precision, bias/error, damage and calibration | Original Request; `src/world/models.py` — Item; `src/world/production.py` — ToolMark | Tasks 1, 5–8; `test_measurement_contracts`, bootstrap and resolution |
| Readings are display observations/evidence, not sampled truth | Original Request; `.ai-factory/ARCHITECTURE.md` — authority/memory principles | Tasks 11, 13–16; audience, provenance and mistaken-reliability tests |
| Engine alone changes instrument condition | `.ai-factory/RULES.md` — axioms 1–2; architecture — objective authority | Tasks 5–10; real admission and replay tests |
| Calibration can be inaccurate; agents need not know true precision/error | Original Request; architecture — owner-scoped beliefs and no truth feedback | Tasks 7, 11, 13; biased-reference and false-confidence examples |
| Temperature, resource amount, elapsed ticks, route-time estimate, load category | Original Request examples; actual `world._physical._ambient`, Resource, RouteSpec and Item.load | Tasks 6, 22; five-dimension real fixture; no physical length/SI mass claim |
| Preserve legacy exact visible quantities/ticks | `src/world/observations.py` — resource/item/self projections | Tasks 11, 20; existing observation and flags-off fixtures |
| Explicit new config/event/pending contracts, not widened v56/v27/v2 | Architecture — versioned extension; runner serializer exact keys; V4-28 pending-v2 | Tasks 3–4, 9–10, 17; canonical old/new fixtures |
| Science remains owner-scoped; physical substrate gains deepening events | Architecture — inward authority; `simulation.v4_architecture` SCIENCE; `versioning` deepening pairs | Task 4 retains authority checks and adds explicit physical-deepening metadata |
| Categorical replication remains categorical; no automatic support promotion | `docs/scientific-replication.md`; `score_remembered_experiment`; `ReplicationMeasurement` | Tasks 14, 16, 20; old replication/hypothesis tests |
| Blank-slate newborns; transactional/fork-safe subjective state | Architecture — entry/checkpoints; `agent_runtime` and `new_agent_initialization` | Tasks 17–20; crash/clone/retirement/newborn tests |
| No new metric families, dashboards, routes, flags or SQL migration required | User scope is physical measurement; architecture requires proven additions | Tasks 12, 23–24; 256-family, 73-semantic and Alembic0017 pins |
| Use admitted-request reading IDs; final event roots arrive after action resolution | `simulation.engine` — event allocation after pending actions; `world._operations.prepare_action_batch` | Tasks 6, 8, 10; real engine/context forwarding and reading/event-ID separation |
| Report actual64-character event/entity IDs without identity truncation | `simulation.identifiers.derive_event_id` / `derive_entity_id`; `agents.cognition.replication_codec` bounded framing | Task 14; complete multipart delivery with generated roots |
| Protect private modules at introduction, recover v3 through actual runner guards | `pyproject.toml` private-world contract; AST checker; `runner._command_from_pending_record`; persistence accepted versions | Tasks 4, 6, 17–18; import and stored-record recovery checks |
| Probe actual newborn measurement content and export retired owners explicitly | `new_agent_initialization` four store/count surfaces; benchmark `STORE_PROBE_PATHS`; runner ledger export pattern | Tasks 19–20; empty/populated probes, real admission and retired export tests |
| Schema2 propagates through nested codecs; scenario holdings satisfy the physical graph | `serialization.decode_domain` / nested codecs; `world._state._validate_graph` and carry checks | Tasks 9, 21–22; nested downgrade rejection and real runner construction for every arm |

### Supported combinations and observable transitions

Every row is a required verification scenario, not a speculative Cartesian product.

| Input / validation | Persisted state | Output / transition | Side effects / invariants | Test owner |
|---|---|---|---|---|
| Spec absent, existing v4 or science v56 | No instrument channel/ledger; old schemas | Original commands and observations | Byte/trajectory parity; Measure denied channel-off | Tasks 3, 8, 20 |
| Valid v57 spec + science prerequisites | Item-keyed instrument/reference records, event28/v26 | Appearance and eligible readings | No automatic measurement or shared beliefs | Tasks 3, 5, 9 |
| Spec under v56, null v57 spec, missing prerequisites, dangling IDs | Nothing committed | Closed validation error | No implicit enabling/default tools | Tasks 1, 3 |
| Own-held healthy tool + eligible local target, d<1000 | Instrument wear after measurement; immutable event reading | Actor display; bystander action only | One action, no target mutation; no sampled truth | Tasks 6, 8, 11 |
| Fine precision + nonzero hidden bias | Same physical bias; display quantization | Consistent but wrong display | Precision does not imply accuracy | Tasks 6, 13, 22 |
| Damaged d<1000 versus broken d=1000 | Wear retained; broken no transition | Degraded display versus denial | No repair through calibration | Tasks 7–8 |
| Reachable matching-unit reference versus missing/wrong-unit/private reference | Replaced correction/revision only on success | Visible adjustment versus denial | Flawed reference can worsen accuracy | Tasks 7–8 |
| Same instrument transferred/stored/corpse-held | Condition and timer unchanged | New holder may act normally | Beliefs do not transfer | Tasks 5, 19–20 |
| Timer versus route-time tool with regional context | Timer epoch; otherwise same instrument state | Elapsed ticks versus current travel estimate | Neither exact wall-clock nor length/future guarantee | Tasks 6, 22 |
| Route-time tool without configured routes | No valid new run or admitted action | Context/target error | Never invent distance/route data | Tasks 3, 8 |
| Direct actor reading versus addressed `msr_v1` report | Own basis versus communicated basis | Qualified owner evidence | No borrowed confidence/support or sender-state copy | Tasks 13–16 |
| Same-root repetition, conflicting reports, unknown conditions | Receipts, retained contradictions/notices | No independent support for repeat | No consensus/truth correction | Tasks 13–14 |
| Proposed action aborted/rejected/replaced | No phantom physical reading/wear | Prior committed observations may still be ingested | Finalize current proposal once | Tasks 15, 18 |
| Live versus checkpoint/suffix replay, noise helper disabled | Exact recorded display/after-state | Identical canonical observations | Replay never resamples/recalibrates | Tasks 9–10, 22 |
| Supported pending recovery, fork, retirement, newborn | Per-owner ledger or empty newborn state | Exact-once restore / isolated divergence | No unsupported durable subjective resume | Tasks 17–20 |
| Instrument plus travel/infrastructure channels | v26 preserves all active inherited fields | Event28 pair wins | Spec absent retains 27/v25 or prior pair | Tasks 9–10 |
| Reading/reference/receipt caps or source loss | Bounded state with explicit notices | Partial/unavailable, never known-empty | No unbounded history or dedup reset | Tasks 13, 17, 22 |
| Generated64-character source IDs and68-character reading IDs in a report | Full original IDs in one bounded1–4-part document | One complete addressed report or atomic rejection | No partial evidence or source-ID substitution | Tasks 14, 22 |
| Domain schema1 parent containing a new command/appearance/event nested below it | Nothing decoded/committed | Explicit cross-version rejection | Children cannot silently upgrade parent | Task 9 |
| Stored pending-v3 versus v1/v2/unknown codec | Version-matched science/measurement payload | Exact supported recovery; unknown rejected | Runner/persistence/run-control accepted sets agree | Tasks 17–18 |
| Full founder inventory versus two available load units | Complete shared items and body inventories or no scenario | Valid runner for every arm versus safe capacity error | No capacity inflation, inconsistent holdings or mutation of base | Task 21 |

## Architecture and Decisions

### Scope and non-goals

Implement five useful measurements over existing physical facts, portable TOOL instruments, ordinary Measure/calibration actions, qualified actor observations, owner-local reliability beliefs, bounded speech reports, and supported replay/finalization lifecycle.

Do not implement instrument manufacturing/recipe expansion, new climate/distance/mass physics, objective scientific truth, globally authoritative calibration standards, numeric hypothesis-language expansion, automatic replication confirmation, statistical accuracy guarantees, global reliability scores, instrument AI actors, new flags, SQL tables, feature-specific HTTP routes, dashboards, overlays or metric families. These are not deferred choices for the implementer; they are outside this increment.

### Authority and placement

- `world.measurement`: frozen public physical/reading contracts. Physical contracts being public does not make them legal cognition inputs.
- `world._measurement`: engine-only sampling/transition/replay; no cognition or analysis imports.
- `simulation.measurement_config`: exact config composition.
- `simulation.measurement_serialization`: physical/domain payload codecs.
- `agents.cognition.measurement*`: owner-safe evidence, interpretation, bounded reports and command proposals.
- `simulation.measurement_checkpoint`: owner state codec, separate from objective replay.
- `experiments.measurement_scenario`: trusted off-gate scenario composition.
- Existing inspection/observer paths expose only their authorized facts. No new production analysis/publication/store feature is needed.

The science context's **belief authority stays owner-scoped**. Engine-owned instruments are its physical substrate, not authoritative scientific knowledge. Keep existing authority validation; the narrow event-use metadata change is specified in Task 4.

### Closed physical records and bounds

`InstrumentState` fields:

`item_id`, `quantity`, `unit`, `nominal_step_milli`, `intrinsic_bias_milli`, `base_error_bound_milli`, `damage_milli`, `correction_milli`, `calibration_state`, `calibration_revision`, `last_adjustment_tick`, `damage_at_adjustment_milli`, `timer_epoch_tick`.

- `nominal_step_milli`: positive integer ≤1,000,000,000.
- Signed bias/correction and source/display/reference values: int64; validate intermediate arithmetic before conversion/storage, never wrap.
- `base_error_bound_milli`: integer 0..1,000,000,000.
- `damage_milli`: integer 0..1000; 1000 is broken.
- Calibration states: `never_adjusted`, `adjusted`, `stale`. `never_adjusted` requires revision0, correction0 and absent last-adjustment/damage-at-adjustment; other states require positive revision and those anchors.
- Timer epoch exists only for duration tools, is nonnegative and not after current tick. Bootstrap default epoch for duration is explicit tick0, not wall-clock.
- `MeasurementReference`: `item_id`, `unit`, `nominal_value_milli`, `physical_value_milli`. Its mark is visible when eligible; its physical value is hidden. This is an abstract modeled passive reference, not a newly simulated thermal bath or standards institution.
- Max64 instruments and max64 references; unique sorted anchors; no shared instrument/reference/STRIKE role on the same item. At least one instrument in a present spec.
- Reference quantities use the same unit scale as the instrument; no automatic conversion between resource units, ticks, Celsius and simulated load.
- `MeasurementUnit` is a frozen value with exact keys `kind` and `resource_unit`. Closed `kind` values are `celsius`, `resource_unit`, `simulated_tick`, `simulated_load`. Only `resource_unit` kind carries the exact original nonempty `Resource.unit` string; all other kinds require `resource_unit=null`. Resource tools/references must match that string exactly; never normalize two labels into one scale. Scalar/category compatibility follows the quantity table.
- Display/target IDs derive from engine-stable IDs; never parse item/location names or use labels as scientific semantics.

`InstrumentAppearance`: quantity, nominal step/unit, wear band (`intact` d<250; `worn` d<750; `damaged` d<1000; `broken` d=1000), and `adjustment_mark_present` bool. The mark says an adjustment occurred, not that current calibration is accurate. No exact damage, bias/noise bound, correction, objective stale flag or reference physical value.

`ReferenceAppearance`: `unit` and `nominal_value_milli` only. It identifies a physical reference and its visible mark for normal owner planning; it does not certify the marked value. `ObservedItem` may carry one of `instrument` or `reference`, never both. Normal own-held/local visibility gates apply, and both fields are omitted in legacy wire rows.

### Quantity and target contract

All source scalars convert to signed integer milli-units using `Decimal(str(existing_scalar))` and half-away-from-zero quantization at the conversion boundary. New calculations must not change old physiology arithmetic.

| Quantity enum value | Target / eligibility | Source / unit | Display |
|---|---|---|---|
| `ambient_temperature` | Actor's current location ID | Existing shared ambient derivation; `celsius` | Signed milli-C scalar |
| `resource_amount` | Eligible visible local resource ID | Current candidate `Resource.quantity`; exact existing resource unit token | Nonnegative milli-unit scalar |
| `elapsed_duration` | The held timer's own item ID | Current sampling tick minus instrument timer epoch; `simulated_tick` | Nonnegative milli-tick scalar |
| `travel_time_estimate` | An observed adjacent route destination ID | Current route-condition duration when travel network is active, otherwise configured `RouteSpec.duration_ticks`; `simulated_tick` | Nonnegative milli-tick scalar; unavailable/closed route rejected |
| `load_category` | Own-held or visibly local ground item ID | Existing `Item.load`; `simulated_load` | `light` (<1000 milli-load), `medium` (<5000), `heavy` (otherwise), after display error/quantization |

Physical distance does not exist in current route models; travel time is the supported example. Load categories are explicitly simulation load, not a claim to SI mass. Legacy exact resource/load/tick/body-temperature facts remain available where they already were.

### Deterministic reading and wear policy

Policy version: `measurement-instruments.v1`. At sampling damage d<1000:

```text
p = nominal_step_milli
b = intrinsic_bias_milli
step = p * (1 + d // 250)
drift = (1 if b >= 0 else -1) * ((p * d) // 1000)
E = base_error_bound_milli + ((abs(b) + p) * d) // 1000
noise = keyed_integer_inclusive(-E, +E)
display = round_half_away_from_zero_to_multiple(x + b + correction + drift + noise, step)
display = max(0, display) for non-temperature quantities
after_damage = min(1000, d + 10)
```

For load-category output apply the table's category thresholds to the resulting internal scalar, then discard that scalar from actor-visible reading data. Precision is the quantization interval; it is not an uncertainty interval.

`keyed_integer_inclusive` uses SHA256 of canonical UTF-8 JSON array `[policy_version, action_tag, seed, derivation_version, physical_rules_fingerprint, stochastic_identity_value_or_null, tick, actor_entity_id, instrument_id, target_id, quantity, calibration_revision, d]`; `sort_keys=True`, compact separators, no NaN; digest big-endian integer modulo `(2*E+1)`, minus E. For E=0 return0. Calibration uses action tag `calibrate_instrument`, measurement `measure`. The engine extracts `stochastic_identity.value` only when present; valid derivation-v1/v2 inputs encode absent identity as JSON null. Use the existing physical-rules fingerprint or null only when physical rules are absent in a valid legacy run. Never substitute run ID, global RNG, wall time, Python hash or an identity inferred from labels. This is a deterministic bounded error model, not a statistical confidence guarantee.

The same input candidate state samples identically in rule evaluation/apply. Only an admitted applied transition wears the tool once. Ordinary ordered current-state resolution still applies to changing target amounts. An unavailable current route condition, closed route, unit mismatch or inaccessible source yields a denied action, never an estimated default.

Private plumbing is explicit: `MeasurementSamplingIdentity` carries only the primitive seed/derivation/fingerprint/optional identity values; `MeasurementRuleContext` carries that identity, sampling tick and frozen actor-entity-keyed eligibility sets. `WorldEngine._measurement_rule_context(snap)` derives eligibility from the token-bound `snap.observation_batch`, then forwards one context through `prepare_action_batch` → `evaluate_operation` / `apply_operation`, including initial and ordered-state checks. Agent commands cannot supply these trusted fields. A tick-start eligible target must still be currently reachable; an initially unseen target cannot gain eligibility merely through an earlier same-tick mutation.

Reading identity is `"msr:" + admitted_request_id.value`, available before rule resolution. It is not a final event ID: existing batch finalization allocates that later. Store the request-derived reading ID in `MeasurementTaken`; the resulting observation separately supplies the actual `source_event_id` for evidence provenance. Replay validates both according to their distinct roles without sampling again.

### Calibration policy

`Measure(instrument_id,target_id,quantity)` and `CalibrateInstrument(instrument_id,reference_id)` are the two new closed commands; count43→45.

Calibration requires an own-held working tool and eligible same-unit held/local reference. Compute the raw reference display with existing intrinsic bias, damage/drift and deterministic calibration noise but **without the old correction**. For category tools use the internal scalar response to the reference before categorization.

```text
new_correction = reference.nominal_value_milli - raw_reference_display
revision += 1
last_adjustment_tick = action sampling tick
damage_at_adjustment = pre-action damage
state = adjusted
apply one use's wear (+10)
if after_damage - damage_at_adjustment >= 100: state = stale
```

Subsequent use makes adjusted calibration stale when damage has risen at least100 since adjustment. It never repairs wear or clears intrinsic bias/noise. Timer calibration also resets its physical epoch to the sampling tick. A successful action proves adjustment only; the reference mark can be wrong and residual error unknown. No automatic correction from sampled target truth.

### Observation and evidence policy

- `MeasurementTaken`: displayed reading plus exact before/after physical transition; actor observation receives the closed reading only.
- `InstrumentCalibrated`: adjustment identity plus exact before/after physical transition; actor sees nominal reference mark and completed adjustment, not physical reference truth/raw response/correction.
- Eligible bystanders see coarse action metadata, not display values. Remote observers receive nothing new.
- Reading ID derives from already-admitted request identity. The later observation separately references the committed event opaquely; cognition never receives a `WorldEvent` or a made-up future event ID.
- Existing memory can remember a display as an experience. It must not assert target equality with that display.
- Own evidence and communicated reports are different bases. Same-root testimony never counts as independent corroboration.

Wire reporting uses one canonical JSON document per report, split into1–4 `CommunicationRelation(subject="msr_v1", predicate="part", object=frame)` atoms. Exact keys are `v`, `report_id`, `instrument_id`, `target_id`, `quantity`, `unit`, `value_kind`, `display`, `nominal_division`, `sample_tick`, `declared_root`, `speaker_confidence_milli`; `v=1`. Scalar `display` is an exact integer, category `display` a closed string; integer slots reject bool. Canonical compact sorted-key ASCII JSON is ≤876 bytes. Full source IDs use `[A-Za-z0-9:_-]{1,128}`: generated64-character IDs and request-derived68-character reading tokens are normal supported inputs, not reasons to skip.

Frame format is `<group32hex>|<index>|<total>|<chunk>`, with index/total1–4,219-character chunks and a37-character header: maximum256 object characters. Group token is the first32 hex characters of SHA256(document), for reassembly integrity only; original source IDs remain full fields inside the document and are never replaced by that digest. Reassemble only complete same-utterance delivery, validate digest/keys/types/version, and reject missing/conflicting/mixed parts atomically. Identical duplicate parts are idempotent. At most one complete report is appended per selected Talk/Tell, only if all parts fit existing enclosing budgets.

Fixed unit tokens are `celsius`, `tick`, `load`; a resource unit is `resource:<exact-unit>` when its original unit string is ASCII `[A-Za-z0-9:_-]{1,32}`. Genuinely unrepresentable units/IDs or oversized documents stay retained locally but skip optional emission; no truncation, guessed escaping, implicit conversion or source-ID hashing.

Owner policy `measurement-beliefs.v1`:

1. First directly observed instrument/display starts confidence500/1000, expected resolution=nominal division, expected error band unknown (`None`).
2. Compare the latest directly acquired prior reading with a different source root only when instrument, target, quantity, unit and owner-observed condition tokens match. Tokens reuse the existing closed observation conditions and exclude absolute tick; unmatched/unknown comparisons leave confidence unchanged.
3. Scalar apparent agreement is absolute difference ≤`2 * max(nominal_divisions)`; category agreement is exact category equality. Agreement adds50 capped950; disagreement subtracts100 floored50. Scalar expected error band becomes observed absolute difference plus max nominal division; category error stays unknown. This is a **subjective heuristic**, never a true error bound.
4. Calibration completion changes cues, not confidence by fiat. Subsequent qualified readings can change appraisal. Recalled or repeated roots cannot reapply a revision.
5. Communicated reports retain source confidence as a declaration and do not directly increment owner instrument confidence. Never obtain true parameters from a report ID/root lookup.
6. Retain128 evidence/report rows combined,64 beliefs,512 revisions,1024 root receipts. Oldest reading rows evict deterministically; bounded receipts are not forgotten to accept duplicates. At receipt cap refuse new evidence with notice. At belief/revision cap retain existing entries, refuse new additions with a corresponding notice. Missing retained evidence is explicitly unavailable.

Receipt identity distinguishes verified own acquisition `(own_observation, source_event_id)` from actual addressed delivery `(communicated, delivery_event_id, report_id)`. Declared-root groups are an additional testimony-independence index, not authority to suppress or replace a later actual own observation. An attacker claiming a future/direct event root cannot consume that direct receipt identity. Every accepted receipt/index addition participates in the same total1024 cap.

Autonomous compilation is conservative: existing non-Wait and replication/hypothesis actions win. At most one instrument proposal on ticks divisible by4; on ticks divisible by16 a confidence≤300 belief plus reachable reference permits calibration first. Otherwise select eligible own-held instrument then target in stable-ID order. A tool already sampled by that owner on the same tick is excluded. Candidate compilation accepts no physical hidden state. `Wait` replacement grants no success or admission shortcut.

### Serialization and compatibility decisions

| Surface | V4-29 contract | Unchanged path |
|---|---|---|
| Runner | New explicit v57 = active v56 family root + exact non-null `measurement_instruments` sibling | v1–v56 old roots; default v4; no new spec means no v57 |
| World replay/checkpoint | Active measurement event28 / codec `v26`, including inherited active fields | Travel27/v25; infrastructure23/v21; all earlier accepted selections |
| Domain envelope | Schema2 for measurement-bearing command/event/observation/export/proposal | Schema1 writes and exact legacy rows remain byte-stable |
| Pending subjective transition | `finalization-command-v3` with `measurement-state-v1` plus existing science state | v1 default; v2 old science; both still accepted unchanged |
| Context map | `v4-context-map-v6` metadata; 17 contexts,12 flags,9 owned/3 unowned | No new context/flag ownership |
| Commands | 45 after two explicit additions | Existing43 tags/meanings preserved |
| Observer | New action kinds alias existing `EXPERIMENT_RESOLVED`;73 semantic types | Protocol/layout unchanged; no private physical details in frames |
| Metrics / API / SQL | 256 families; `/v1`; Alembic0017 | No new metric family, route, store or migration |
| Science | Numeric/category reading evidence stays separate | `hyp_v1`, categorical `rep_v1`, replication snapshot/store/routes unchanged |

New physical codecs must reject data the selected older schema cannot represent. Reserved epidemic/ecology/disaster pairs stay reserved. No “latest” change is permission to rewrite legacy archives.

`required_domain_schema` recursively selects the parent domain envelope once. Thread explicit `wire_schema` through top-level and nested command/proposal/observation/world-event/export encode/decode calls; children cannot auto-upgrade an envelope1 parent. Journal event-detail calls remain governed by event/persistence versions, not a fabricated domain wrapper.

Pending recovery must extend both run-control and persistence accepted sets and `runner._command_from_pending_record`'s real stored-record guard. v3 retains v2's required experiment/replication envelopes plus measurement; it cannot silently skip an old science payload. `SimulationRunner.export_measurement_ledgers()` provides owner-ordered active/retired committed ledgers for trusted callers; result-v2/v3 JSON is not widened.

## Phase Index

1. [Phase 1: Contracts and configuration](phase-01-contracts-and-configuration.md) — Tasks 1–4
2. [Phase 2: Physical resolution](phase-02-physical-resolution.md) — Tasks 5–8
3. [Phase 3: Replay and owner-safe perception](phase-03-replay-and-perception.md) — Tasks 9–12
4. [Phase 4: Owner-scoped measurement evidence](phase-04-owner-evidence.md) — Tasks 13–16
5. [Phase 5: Finalization, recovery and lifecycle](phase-05-finalization-and-lifecycle.md) — Tasks 17–20
6. [Phase 6: Experiments, documentation and completion gates](phase-06-experiments-docs-and-gates.md) — Tasks 21–24

## Cross-Phase Dependencies

- Task2 depends on1; Task3 on1–2; Task4 on3.
- Task5 depends on1,3–4; Task6 on5; Task7 on6; Task8 on2,5–7.
- Task9 depends on4,8; Task10 on9; Task11 on8–10; Task12 on11.
- Task13 depends on1,11; Task14 on13; Task15 on13–14; Task16 on15.
- Task17 depends on15–16; Task18 on17; Task19 on18; Task20 on19.
- Task21 depends on3,8,16,20; Task22 on10–12,18–21; Task23 on22; Task24 on1–23.
- Execute in index order. Every phase is a coherent implementation checkpoint, not an authorization to omit later co-landing gates.

## Tasks

### Phase 1: Contracts and configuration

- [x] Task 1: Define instrument and reading contracts ([details](phase-01-contracts-and-configuration.md#task-1-define-instrument-and-reading-contracts))
- [x] Task 2: Add explicit measurement and calibration commands ([details](phase-01-contracts-and-configuration.md#task-2-add-explicit-measurement-and-calibration-commands)) (depends on 1)
- [x] Task 3: Add the exact runner-config-v57 instrument seam ([details](phase-01-contracts-and-configuration.md#task-3-add-the-exact-runner-config-v57-instrument-seam)) (depends on 1, 2)
- [x] Task 4: Register the physical deepening version contract ([details](phase-01-contracts-and-configuration.md#task-4-register-the-physical-deepening-version-contract)) (depends on 3)

### Phase 2: Physical resolution

- [x] Task 5: Bootstrap item-keyed instrument and reference state ([details](phase-02-physical-resolution.md#task-5-bootstrap-item-keyed-instrument-and-reference-state)) (depends on 1, 3, 4)
- [x] Task 6: Implement fixed-point sampling and deterministic display error ([details](phase-02-physical-resolution.md#task-6-implement-fixed-point-sampling-and-deterministic-display-error)) (depends on 5)
- [x] Task 7: Resolve imperfect physical-reference calibration ([details](phase-02-physical-resolution.md#task-7-resolve-imperfect-physical-reference-calibration)) (depends on 6)
- [x] Task 8: Co-land admission, operations, costs and events ([details](phase-02-physical-resolution.md#task-8-co-land-admission-operations-costs-and-events)) (depends on 2, 5, 6, 7)

### Phase 3: Replay and owner-safe perception

- [x] Task 9: Version physical snapshots and strict domain envelopes ([details](phase-03-replay-and-perception.md#task-9-version-physical-snapshots-and-strict-domain-envelopes)) (depends on 4, 8)
- [x] Task 10: Implement effect-complete replay and checkpoint restoration ([details](phase-03-replay-and-perception.md#task-10-implement-effect-complete-replay-and-checkpoint-restoration)) (depends on 9)
- [x] Task 11: Project readings and appearances without hidden accuracy ([details](phase-03-replay-and-perception.md#task-11-project-readings-and-appearances-without-hidden-accuracy)) (depends on 8, 9, 10)
- [x] Task 12: Keep inspection and observer output read-only and redacted ([details](phase-03-replay-and-perception.md#task-12-keep-inspection-and-observer-output-read-only-and-redacted)) (depends on 11)

### Phase 4: Owner-scoped measurement evidence

- [x] Task 13: Add a bounded owner reading and reliability ledger ([details](phase-04-owner-evidence.md#task-13-add-a-bounded-owner-reading-and-reliability-ledger)) (depends on 1, 11)
- [x] Task 14: Add bounded measurement testimony without borrowed accuracy ([details](phase-04-owner-evidence.md#task-14-add-bounded-measurement-testimony-without-borrowed-accuracy)) (depends on 13)
- [x] Task 15: Integrate candidate measurement state into the cognitive loop ([details](phase-04-owner-evidence.md#task-15-integrate-candidate-measurement-state-into-the-cognitive-loop)) (depends on 13, 14)
- [x] Task 16: Bridge physical evidence and compile conservative instrument actions ([details](phase-04-owner-evidence.md#task-16-bridge-physical-evidence-and-compile-conservative-instrument-actions)) (depends on 15)

### Phase 5: Finalization, recovery and lifecycle

- [x] Task 17: Add measurement-state-v1 and pending finalization v3 ([details](phase-05-finalization-and-lifecycle.md#task-17-add-measurement-state-v1-and-pending-finalization-v3)) (depends on 15, 16)
- [x] Task 18: Commit and recover measurement state atomically ([details](phase-05-finalization-and-lifecycle.md#task-18-commit-and-recover-measurement-state-atomically)) (depends on 17)
- [x] Task 19: Preserve owner-safe checkpoints, forks and retirement ([details](phase-05-finalization-and-lifecycle.md#task-19-preserve-owner-safe-checkpoints-forks-and-retirement)) (depends on 18)
- [x] Task 20: Enforce blank-slate admission and spec-off parity ([details](phase-05-finalization-and-lifecycle.md#task-20-enforce-blank-slate-admission-and-spec-off-parity)) (depends on 19)

### Phase 6: Experiments, documentation and completion gates

- [x] Task 21: Register a reproducible measurement opportunity experiment ([details](phase-06-experiments-docs-and-gates.md#task-21-register-a-reproducible-measurement-opportunity-experiment)) (depends on 3, 8, 16, 20)
- [x] Task 22: Prove the full physical-reading-evidence lifecycle ([details](phase-06-experiments-docs-and-gates.md#task-22-prove-the-full-physical-reading-evidence-lifecycle)) (depends on 10, 11, 12, 18, 19, 20, 21)
- [x] Task 23: Complete the mandatory documentation checkpoint ([details](phase-06-experiments-docs-and-gates.md#task-23-complete-the-mandatory-documentation-checkpoint)) (depends on 22)
- [x] Task 24: Run compatibility, architecture and quality gates ([details](phase-06-experiments-docs-and-gates.md#task-24-run-compatibility-architecture-and-quality-gates)) (depends on 1–23)

## Commit Plan

Suggested checkpoints only; do not create commits without explicit authorization.

1. After Tasks1–4: `feat(measurement): define instrument contracts and versioned configuration`
2. After Tasks5–8: `feat(world): resolve fallible measurements and physical calibration`
3. After Tasks9–12: `feat(replay): persist instrument state and project qualified readings`
4. After Tasks13–16: `feat(cognition): retain measurement evidence and fallible reliability beliefs`
5. After Tasks17–20: `feat(runtime): finalize and recover owner measurement state`
6. After Tasks21–24: `test(measurement): add research scenarios documentation and compatibility gates`

## Definition of Done

- All24 tasks pass their acceptance checks; linked phases and progress ledger agree.
- Physical tools have precision, bias/error, persistent damage and fallible calibration; all five useful dimensions have real admitted-action tests.
- At least one agent trusts an inaccurate instrument and at least one calibration worsens accuracy without truth feedback.
- Displays become qualified actor observations/evidence, not target truth; communicated evidence retains its source distinction.
- Live/restored displays and physical state are identical; supported subjective finalization/recovery/forks/retirement preserve owner privacy.
- No-spec legacy fixtures retain bytes/trajectory; default writes and old accepted versions remain executable.
- Full mandatory Python/static/architecture gates pass with coverage; docs checkpoint completes. Optional DB/client/browser/scale lanes are explicitly passed, failed or unexecuted.
- No unsupported scientific accuracy, subjective resume, emergence, capacity or infrastructure certification claim.

## Risks and non-blocking limits

- New physical actions and record fields require a substantial co-landed versioned extension; merely changing `ExperimentResolved` is insufficient.
- Existing resource/load/tick exposure limits what can honestly be called newly unknown. This plan preserves those contracts instead of changing the epistemology of the entire simulator.
- Interval timers and route estimates are bounded simulation measurements, not physical distance or future arrival guarantees.
- Current categorical scientific hypotheses/replication do not gain a new numeric predicate language; reading evidence is retained independently.
- Ordinary autonomous policy may never use a tool because higher-priority actions win. That is a legal null; controlled tests demonstrate mechanism separately.
- The abstract physical reference can itself be biased. Calibration success never guarantees accuracy.

## Open Questions

None blocking within the declared scope. The numerical policies and caps above are explicit initial model choices, version-locked and covered by golden fixtures; changing them later requires a policy/version decision, not silent tuning.

## Refinement Record

Approved `$aif-improve` pass on2026-11-18; no new tasks, deletions, status changes or dependency changes:

1. Task14 now uses bounded multipart testimony preserving real full-size IDs.
2. Tasks6/8/10 explicitly carry engine-owned eligibility/sampling context and separate admitted-request reading IDs from later event correlation; owner-visible reference marks make ordinary calibration planning possible.
3. Tasks4–6/24 co-land both private-module boundary registries with new imports.
4. Tasks17–18 update persistence/version mirrors and the actual runner pending-record recovery gate.
5. Tasks19–20 specify active/retired ledger export and all actual-content blank-slate/probe surfaces.
6. Task9 propagates domain envelope versions recursively and preserves the separate journal event-detail path.
7. Tasks21–22 build complete holder/inventory/capacity-consistent scenario worlds and prove them through real runner construction/execution.

The Original Request block and all24 task IDs/statuses are preserved exactly. No application code or external requirement artifact was changed by refinement.

## Completion Notes (2026-11-18)

Status: all 24 tasks complete. Mandatory local gates are green; optional environment-bound lanes remain unexecuted.

Verified local gates so far:

- `ruff check src tests` — pass.
- `mypy src tests` — pass (2936 files).
- `lint-imports` — 25 contracts kept.
- `pytest tests/unit/test_measurement_*.py tests/unit/test_runner_config_v57.py` — 126 passed.
- `pytest tests/architecture` — 721 passed.
- `pytest tests/unit` — 11,763 passed, 1 skipped.
- Task-specific measurement suites — 126 passed.
- `pytest tests/unit/test_v1_regression_gate.py` — 11 passed.
- Focused replication recovery/checkpoint, V4 versioning, blank-slate, and scenario suites pass.

Changed current pins: 45 commands, event 28 / codec `v26` when the measurement
channel is active, `runner-config-v57` accepted, `v4-context-map-v6`, pending
`finalization-command-v3`. Metric families stay 256, observer semantic types 73,
Alembic `0017`, `/v1`, `observer-protocol-v1`.

Environment-bound lanes remain unexecuted: the PostgreSQL/durable measurement
journal integration test, Compose/browser acceptance, the pinned Godot client
protocol run, and benchmark/scale lanes. No commit or push was performed. The
final full-suite run did not enable a separate coverage report; focused feature
runs used `--cov` during implementation.

## Verification Remediation (2026-11-18)

An `$aif-verify` pass found and corrected functional gaps without changing the
plan contract or task IDs:

- v57 trusted composition now enables the owner measurement channel
  (`measurement_enabled`) for initial, mid-run and newborn loops.
- `msr_v1` reports are now selected and attached to existing `Talk`/`Tell`
  within the existing relation budget.
- Direct readings feed the existing owner evidence bridge.
- Replay schema 28 accepts inherited `route_condition_changed` events.
- Travel-time measurement denies a missing route instead of inventing 1000 ms.
- Observed wear/adjustment cues refresh owner reliability beliefs.
- Replay rejects a reading whose quantity/unit differs from the instrument.
- Measurement state/reference role conflicts and initial epoch bounds are
  validated; v3 stored-record recovery is exercised through the real runner
  guard.
- Missing focused suites were added: loop composition, fork/retirement export,
  lifecycle/probe counts, pins/docs, architecture boundaries and the opt-in
  durable journal lane.
- The four scenario arms are constructed through a real runner; the v57
  end-to-end test asserts admitted readings and populated owner ledgers.
- Current metric-catalog wording was corrected across touched docs.

The durable journal test remains opt-in and is skipped without
`PALIMPSEST_TEST_DATABASE_URL`; no certification claim is made for unexecuted
environment-bound lanes.

