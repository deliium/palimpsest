# Phase 1: Observational evidence foundation

Plan: [index.md](index.md)  
Tasks: 1–3  
Depends on: none

## Objective

Capture what an owner actually carries at finalized boundaries, without changing cognition, commands, admission, replay, or stopping. Historical audit occurrences must not masquerade as current possession.

## Current-Code Evidence

| Path | Symbols / lines | Why it matters |
|---|---|---|
| `src/agents/cognition/cultural_features.py` | `SubjectiveCulturalBelief`, `CulturalFeatureLedger`, `CulturalFeatureAudit`, `collect_cultural_feature_public_cues` | Beliefs have full fingerprints, local parents and evidence; audits have only truncated tokens and counts. Communication cue fingerprints include speaker metadata and are not universal semantic equivalence keys. |
| `src/agents/cognition/practical_knowledge.py` | `SubjectivePracticalKnowledge` | Has active state, full fingerprint, source/teacher, parent entries and acquisition tick. |
| `src/agents/cognition/semantic_naming.py` | `LabelBinding`, `TerminologyLedger` | Label inventories, status and sense history are distinct from cultural term audits. |
| `src/simulation/agent_runtime.py` | `_commit_cultural_features`, `_commit_practical_knowledge`, `export_cultural_narratives`, `export_runtime_checkpoint` | Runtime carries ledgers after subjective finalization. Do not export a whole checkpoint to analysis. |
| `src/simulation/runner.py` | `run_tick` 2697–2714, `_record_finalized_tick`, `recover_pending_finalizations` | New entries synchronize before finalization; boundary capture must follow all owner finalizations. |
| `src/simulation/runner.py` | `recover_pending_finalizations` 2936–3111, `restore_runtime_checkpoint` | Recovery starts runtimes before resolving pending state and synchronizes entrants after finalization; publication cannot be inserted blindly into `_ensure_started` or `_record_finalized_tick`. |
| `src/analysis/models.py` | `MetricDocument`, `MetricCoverage`, `MetricProvenance` | Values are scalar-only; evidence detail needs a canonical JSON-string value or separate artifact. |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `src/simulation/cultural_evidence.py` | create | Neutral frozen research-export DTOs and sink protocol; no analysis import. |
| `src/simulation/agent_runtime.py`, `src/simulation/runner.py` | modify | Owner exports and optional finalized-boundary sink. |
| `src/simulation/__init__.py` | modify | Export only the new documented contracts. |
| `src/analysis/cultural_evolution_evidence.py` | create | Validated analysis inputs, stable normalization and provenance registry. |
| `src/experiments/cultural_evidence.py` | create | Bounded recorder and outer-layer conversion. |
| `src/experiments/cultural_evidence_serialization.py` | create in Task 3 | Strict normalized-evidence codec and digest, available before metric assembly. |
| `tests/unit/test_cultural_evolution_evidence.py`, `tests/unit/test_cultural_evidence_capture.py` | create | Evidence validation, capture lifecycle and parity tests. |

## Task 1: Define detached cultural evidence contracts

### Intent

Make complete-empty, missing, disabled and incomplete inventories distinguishable before implementing any ratio.

### Implementation Steps

1. Introduce frozen, defensively detached DTOs in `simulation.cultural_evidence`: `CulturalChannelExport(channel, enabled, coverage, basis, ledger)`, `CulturalOwnerExport(owner_id, generation_index, living, channels)` and `CulturalBoundaryExport(run_id, boundary_tick, owners)`. The four closed channels are `cultural_features`, `terminology`, `narratives`, `practical_knowledge`. Coverage is `complete`, `missing` or `disabled`; basis is `carried_ledger`, `fresh_empty`, `restored_ledger`, `unavailable` or `channel_off`. Ledger fields contain only the corresponding existing immutable owner-local ledger or `None`; never world state, runtime objects, engine, prompts or memory stores. Verify ledger immutability; defensively detach mutable nested members. Use safe custom repr or `repr=False` for all payload-bearing fields.
2. Add `CulturalBoundarySink.capture(frame) -> None` as a synchronous protocol. The implementation is an observational recorder, not a policy callback. It cannot return commands or stop decisions. Do not add an evidence-stage enum, runner-config field or result codec field.
3. In `analysis.cultural_evolution_evidence`, introduce frozen `CulturalEvolutionInputs`, `InventoryBoundary`, `TraitPresence`, `TransmissionEdge`, `GroupMembership`, `ArchiveKnowledgeState`, `EvidencePointer` and `CulturalMeasurement`. Require explicit `run_id`, revision, window start/end, policy `cultural-evolution.v1` and expected boundary interval (one tick).
4. `InventoryBoundary` records boundary tick, living owner roster, generation map, per-owner/per-dimension coverage (`complete`, `missing`, `disabled`), and present entries. `TraitPresence` includes owner, local entry ID, dimension, exact content digest, lineage key if evidenced, acquisition tick, parent refs, source refs and existing active/status value. Retain raw structured fingerprints only inside the conversion call; store full SHA-256 digests, not audit prefixes or prose.
5. `EvidencePointer` identifies `(run_id, owner_id, boundary_tick, source_kind, local_id, source_revision_digest)` plus original opaque evidence refs. Freeze the exact measurement schema in the contract below; metric keys are not unique row IDs. Preserve population-roster evidence for zero/absence measurements as well as pointers to present entries.
6. Validate exact integers (reject booleans), finite values, unique identities, owner consistency, boundary monotonicity, no future evidence, generation integers and exact allowed dimension/status strings. Resolve duplicate identical rows idempotently; contradictory rows sharing an identity fail with `cultural_evidence_conflict`.

### Required Interfaces and Contracts

- Dimensions are namespaced: six existing cultural feature kinds as `feature:<kind>`, plus `vocabulary`, `narrative`, `technology`. Never silently equate a term audit with a vocabulary binding or a production-technique belief with practical knowledge.
- `enabled=False` requires `coverage=disabled`, `basis=channel_off`, `ledger=None`. Enabled plus a validated carried/restored ledger is complete, including an empty ledger. Enabled plus `ledger=None` is complete only with `basis=fresh_empty` and positive evidence that this owner is freshly initialized with no carried content; otherwise it is missing/unavailable. A previously carried/restored ledger that disappears must never be relabeled fresh-empty. Export enablement from actual bound channel spec/mode, not ledger presence, including newborn runtime modes.
- Boundaries use state-after-finalization: state at boundary `b` follows ticks `< b`. Baseline 0 is pre-first-tick state. This seam is independent of legacy metric-service inclusive event windows; conversion must explicitly use `[start, end)` for objective events.
- Define `CulturalAnalysisWindow(baseline_boundary=0, end_boundary=None)`: baseline is an exact nonnegative boundary; explicit end must be greater than baseline; `None` resolves to the run's actual last fully finalized boundary. Never substitute the first complete/nonempty frame for a requested baseline. A missing requested boundary yields unavailable endpoint/cohort results; an empty baseline yields zero baseline counts and null cohort-retention shares. The request and resolved bounds are retained in evidence identity.
- All source fingerprints are domain-separated full hashes of canonical exact source values. No fuzzy clustering, language inference, truncated digest matching or investigator-defined truth correction.
- Safe repr reveals IDs/counts/status only; never ledger content, labels, digest values or evidence payloads.

### Frozen Measurement Schema

Every serialized measurement has exactly these keys; optional values are explicit nulls, not omitted keys:

| Field | Type / meaning |
|---|---|
| `row_id` | Full domain-separated SHA-256 identity of the scientific selector tuple below; never reused as a metric key. |
| `measurement_id` | Stable formula key from Tasks 4–9 (for example `trait_frequency` or `exact_fidelity`); family-qualified by the containing document. |
| `dimension`, `representation` | Closed namespace dimension and representation (`ledger_carriage`, `label_inventory`, `narrative_lineage`, `practical_content_key`, `practical_variant`, `transmission_edge`). |
| `scope`, `partition_id`, `group_ids` | Scope `global`, `group`, `group_pair`, `owner`, or `edge`; nullable partition; canonically sorted tuple of zero, one, or two group IDs. |
| `population_basis`, `denominator_code` | Stable formula-specific codes, not counts or prose; distinguish eligible living owners, carrier incidences, fixed baseline traits, fixed eligible pairs, attributable acquisitions and comparable single-source edges. |
| `baseline_tick`, `end_tick` | Exact resolved boundary integers; point measurements use equal bounds. |
| `trait_id`, `lineage_id`, `subject_id` | Nullable detailed selectors; owner/edge identities belong in `subject_id`, never in a cross-run population summary. |
| `units` | `count`, `proportion`, `nats`, `effective_traits`, `jaccard_distance`, `ticks`, or `generations`. Entropy/JS use nats; bounded shares use proportion. |
| `value`, `numerator`, `denominator` | Finite numeric or null; numerator/denominator null for entropy and other nonratio estimands. Reject booleans as numeric values. |
| `availability`, `reason_code` | Existing metric availability vocabulary plus nullable safe reason code. A complete row is `PRESENT`; partial values are never passed off as exact population estimates. |
| `coverage_observed`, `coverage_expected` | Exact nonnegative counts for that row's declared denominator unit, nullable only when expected coverage is unknown. |
| `left_censored`, `right_censored` | Explicit booleans; gaps retain their own reason codes and evidence registry entries. |
| `evidence_ids` | Sorted unique tuple of normalized evidence-pointer IDs, including roster/coverage/absence witnesses where applicable. |

The selector tuple for `row_id` is `(family, algorithm_version, policy_version, measurement_id, dimension, representation, scope, partition_id, group_ids, population_basis, denominator_code, baseline_tick, end_tick, trait_id, lineage_id, subject_id, units)`. Hash it as canonical JSON; source values and evidence pointers are not part of row identity. Contradictory values for the same row ID are errors. Comparison keys use the scientific selector, never run-local `row_id` or source IDs. Formula keys and allowed units/denominator codes are enumerated alongside the six specifications in Task 10; all unspecified combinations fail closed.

### Requirement Evidence

User: agent-level provenance and quantitative cultural metrics; `.ai-factory/RULES.md` axioms 1–6; architecture §§Dependency Rules, Memory/testimony, Versioned Extension Contract. Verify all supported input states in the index reconciliation table.

### Error Handling and Logging

DTO constructors raise safe `TypeError`/`ValueError` codes, never repr of rejected payloads. No constructor logging. Recorder logs only boundary counts, row counts and safe failure codes.

### Tests

`tests/unit/test_cultural_evolution_evidence.py`: missing versus explicit empty; enabled-but-uninitialized versus fresh-empty versus restored-empty; disabled versus unsupported; digest collision-prefix examples; malformed owners, negative/future ticks, NaN, duplicate conflicts, mutable input detachment and safe repr. Round-trip exact measurement fields, units/denominator codes, stable formula keys versus row IDs, null-ratio fields and zero-state roster evidence.

### Acceptance Criteria and Verification

Every measurement can name its underlying owner-local rows; empty and unknown evidence are distinguishable after serialization. Run `uv run pytest tests/unit/test_cultural_evolution_evidence.py --cov=analysis --cov=simulation --cov-report=term`; all cases pass.

## Task 2: Capture finalized inventories without behavioral effects

### Intent

Obtain longitudinal inventories rather than retrospectively filling missing history from final snapshots.

### Implementation Steps

1. Add `AgentRuntime.export_cultural_owner_state()` returning its four channel exports, including actual bound enablement and evidence-backed coverage from Task 1. Use existing narrative export behavior and new direct owner-safe accessors for cultural features/practical knowledge/terminology. Track initialization provenance explicitly so restored missing state cannot be confused with fresh-empty state. Validate ownership in simulation, not in a live analysis call.
2. Add `SimulationRunner.set_cultural_boundary_sink(sink)`, installed once before first execution or before checkpoint restoration; `None` is the default. A sink remains installed across restoration, while the runner's observational capture cursor is reset to unknown-prefix status for the restored boundary. Reject replacement after execution starts. Add `export_cultural_capture_status()` returning a neutral frozen `CulturalCaptureStatus(active, failed, failure_boundary, failure_code, missing_prefix_through)`; it remains queryable even if the exporter/sink itself raises. Build the roster from currently admitted runtimes plus lifecycle facts, not `config.agents` alone. Preserve deceased owner references for provenance but mark them nonliving.
3. Factor a common `_publish_cultural_boundary_if_complete` helper, but call it only after each path's synchronization/finalization requirements. In a fresh run publish boundary 0 before first preparation only after proving no pending objective/subjective work. Do not publish from `_ensure_started`, which recovery also calls. Normal `run_tick` publishes after entrant synchronization, `_finalize_and_acknowledge` (including goal receipts), and cursor advancement. Pending recovery publishes only after `_finalize_and_acknowledge` AND `_sync_mid_run_population_entries`. A cursor-only `OBJECTIVE_REPLAY` or recovery without all owners' state never proves a complete cultural boundary. Mark missing coverage rather than exporting the current engine state under an older boundary label. Multi-tick recovery publishes only boundaries for which the exact contemporaneous owner state is available; never backfill intermediate frames from the final state.
4. Frame contents are detached values. Do not pass engine/runtime references to the sink. Sinks must only store frames; invoke normalization and metrics after execution, never in the live cognition path.
5. Add `CulturalEvidenceRecorder(max_frames=10000, max_rows=1000000)` in experiments. Retain boundary 0 and subsequent frames until either cap is reached; record an explicit gap/`capture_truncated` and ignore later frames. Do not evict old frames or manufacture endpoint coverage. Count the actual ledger entries retained across frames against the row cap.
6. On exporter/sink exception, update runner-owned `CulturalCaptureStatus` first, disable further capture and continue simulation. Emit a safe warning without the exception body. After execution and before leaving the runner context, merge `export_cultural_capture_status()` into the recorder's detached result; a broken sink is not responsible for recording its own failure. Restored execution begins at the real complete restored boundary, with an explicit missing prefix; it never publishes boundary 0. No checkpoint/SQL extension is introduced, and restoration does not imply durable cultural capture history.

### Required Interfaces and Contracts

Capture is composition-only and default off. Disabled runs must not allocate frames, normalize digests or emit new metric families. Capture never changes RNG consumption, IDs, existing result documents, objective events, termination or `prepare_parallel=False`. Boundary duplicates must be identical or become an evidence conflict; never duplicate prevalence counts. The output is historical inspection evidence, not subjective restart state.

### Error Handling and Logging

Capture failures affect availability, not world commit. A recorder is marked failed before any warning is emitted. DEBUG logs contain boundary and entry counts; WARN contains `capture_failed`/`capture_truncated` only, no exception payload or fingerprints.

### Tests

`tests/unit/test_cultural_evidence_capture.py`: on/off objective-event and command parity, baseline and final boundary inclusion, newborn admission and death, no publication after failed finalization, recovery deduplication, late capture censoring, recorder cap and sink/exporter exception isolation with persisted failure status. Exercise real checkpoint export/restore with sink installed before restore, crash after objective commit and partial owner finalization, newborn synchronization during recovery, cursor-only objective replay, and no fabricated prefix/intermediate frames. Use deterministic fakes and a real existing generational base for admission coverage; do not substitute a hand-built restore map.

### Acceptance Criteria and Verification

Captured runs have exactly one complete frame per successfully captured finalized boundary, and uncaptured trajectories are unchanged. Run `uv run pytest tests/unit/test_cultural_evidence_capture.py tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py --cov=simulation --cov-report=term`.

## Task 3: Normalize snapshots and attributable transmission evidence

### Intent

Commit conservative, reproducible mappings from source ledgers into analytical rows.

### Implementation Steps

1. Implement `cultural_evolution_inputs_from_capture(...)` in `experiments.cultural_evidence`; delegate pure validation and normalizers to analysis. Inputs include captured frames, committed events, explicit generation/kinship facts, optional detached community memberships and optional archive states. The function is called only after execution.
2. Cultural beliefs count as carried inventory while retained in the ledger; call this `ledger_carriage`, not durable internalization. Eviction changes inventory presence, not proven forgetting. Preserve the original feature kind and exact full fingerprint. Naming uses `LabelBinding.label_token` only for `NamingStatus.ACTIVE` with `merged_into is None`, not referent equality; candidates and retired/merged bindings are excluded. Narratives use active variants and explicit ancestry. Technology uses active practical entries and their source content keys.
3. Emit acquisition candidates once per `(owner, source_kind, local_id, acquired_tick)`; reinforcement audits do not create additional transmission opportunities. In-place fingerprint changes become revision transitions, not invented donor transfers.
4. Build cross-owner edges only from explicit `source_agent_id`/`teacher_agent_id`, exact parent entry identity and supported provenance refs in practical knowledge or equally explicit existing narrative/naming evidence. Resolve source state at or before acquisition, never from a later source revision. Multiple possible source rows yield `ambiguous_source`, not nearest-match selection. Generic cultural audit channels alone do not establish edges.
5. Classify attributable edges by numeric generation: same generation horizontal; source generation lower than receiver intergenerational; higher-to-lower reverse-intergenerational; unknown separately. `vertical_kin` additionally requires an explicit objective parent→child edge. An older teacher is not automatically a parent. Artifact-mediated transmission stays a separate modality and is not horizontal/vertical without an evidenced source.
6. Build stable opaque evidence pointers to exact source/recipient rows and retain unresolved/ambiguous counts. Source lineage claims stay testimony; distinguish an explicit claimed link from a resolved matching donor state. Fidelity requires the latter. No matching based only on shared content, region, hop count, similarity or simultaneous acquisition.
7. Introduce `src/experiments/cultural_evidence_serialization.py` here, not in Task 11. Freeze `cultural-evolution-evidence-v1` and its exact-key normalized envelope: `schema_version`, `run_id`, `config_fingerprint`, `source_revision`, `policy_version`, `capture_options`, `analysis_window`, `boundaries`, `trait_rows`, `transmission_edges`, `group_memberships`, `archive_states`, `evidence_pointers`, `gaps`, `capture_status`, `digest`. Serialize immutable normalized DTOs only; no metric documents or measurement values enter this evidence payload. Compute `digest` over canonical JSON excluding only `digest`; this makes evidence identity available before Task 10 and avoids any metric/evidence digest cycle. Use sorted collections, compact separators, UTF-8, no nonfinite numbers and duplicate-aware JSON decoding. Task 11 reuses the codec; it owns filesystem writes, not a second encoding implementation.

### Required Interfaces and Contracts

`TransmissionEdge` includes edge ID, source/receiver refs, acquisition boundary, modality, attribution status, generation class, kin status, comparable source/target digests and mutation/recombination annotations. Domain ledgers are never rewritten. Group memberships are detached analysis inputs with explicit boundary, membership basis/version and evidence refs; no inferred groups are fed back to cognition.

Acquisition tick `t` occurs during tick t: the receiver's post-acquisition inventory is observed at boundary t+1. A donor snapshot at boundary <=t can witness pre-acquisition source state; a later snapshot cannot be borrowed merely because the entry's original acquisition tick is older. Use later source evidence only when explicit revision lineage proves the relevant version. Normalized evidence stores the requested window and resolved endpoint; no caller may substitute a later/first-complete baseline. Encoder/decoder errors use payload-free codes; no duplicate-key text is logged.

### Error Handling and Logging

Malformed structural evidence fails validation; absent attribution is a legitimate excluded observation. Log only normalized row and exclusion counts. Missing population or archive coverage must remain missing.

### Tests

Extend evidence tests: local parent ID collisions across owners; two donors; same-tick versus later source revision and boundary t/t+1 distinction; same-root repeated reports; independent rediscovery; generic communication with no source link; known practical teacher; numeric generations 2 versus 10; unrelated older teacher; verified parent/child. Add evidence-codec round-trip, duplicate-key rejection, canonical digest stability, changed-row digest change and absence of any metric-document dependency.

### Acceptance Criteria and Verification

Known provenance yields reproducible edges; unsupported provenance yields explicit unknowns rather than fabricated transmission. Run `uv run pytest tests/unit/test_cultural_evolution_evidence.py tests/unit/test_cultural_feature_audit_harvest.py --cov=analysis --cov=experiments --cov-report=term`.

## Phase Risks and Mitigations

- Ledger bounds and late capture can look like extinction: preserve gaps and restrict all extinction claims to complete inventories and explicit carriage semantics.
- Existing evidence may not resolve donors: publish coverage/exclusions and compute only applicable rates; never change cognition to improve metric availability.
- Extra exports could leak private content: trusted outer capture only, safe repr, no HTTP/client exposure and no payload logging.

## Phase Completion Checklist

Every Task 1–3 meets its acceptance criteria; verification commands pass; update task checkboxes only in `index.md`.
