# Implementation Plan: V3-27 Cross-Cultural Translation

Branch: main (current branch; `git.create_branches: false`)
Created: 2026-10-18
Mode: full (ultra depth requested)

## Settings

- Testing: yes
- Logging: verbose
- Docs: yes — mandatory `/aif-docs` checkpoint during implementation.
- Artifact naming: every plan artifact produced for this feature begins `v3-`; canonical file is `.ai-factory/plans/v3-27-translation.md`.
- Implementation scope: owner-scoped, bounded inference of mappings between foreign terms and an agent's own active terms. Agents may learn mappings through shared observation, demonstration, repeated interaction, teaching, artifacts, and context. Mappings carry confidence and provenance; they may be resolved, partial, ambiguous, or wrong, and only detached analysis may call an outcome exact or wrong. Mistranslation may enter the normal communicated-memory/testimony and social-action paths. Detached analysis measures cross-group communication accuracy. **No objective dictionary, no shared lexicon authority, no world behavior, no new command, no new event, no new perception field, no new observer semantic type, no new replay/codec pair, no Alembic migration, no new capability flag.**

## Roadmap Linkage

Milestone: "M7 — V3 Generational Civilization"
Rationale: Extends the owned cultural-contact, naming, symbolic-language, and semantic-drift substrate so separately developed vocabularies can be partially bridged by the agents themselves, while meaning, confidence, ambiguity, and error remain subjective and analysis stays detached.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] full mode confirmed; git.create_branches=false; resolved plan file: .ai-factory/plans/v3-27-translation.md (format=slug)
INFO [aif-plan] plan_default_milestone=auto surfaces M6 first; explicit V3 scope uses M7, following v3-22/v3-23/v3-24/v3-25/v3-26 precedent; this plan does not close M6
INFO [aif-plan] ultra request treated as full-mode depth; this skill has no separate ultra mode
INFO [aif-plan] RESEARCH.md absent; research_influenced_plan=false
INFO [aif-plan] baseline selectors to recheck before implementation: 43 commands, 73 observer semantic types, 109 metric families, runner-config-v46, replay-v22/codec v20, Alembic 0017, latest Experiment BC
INFO [aif-plan] target selectors after this plan: 43 commands, 73 observer semantic types, 112 metric families, runner-config-v47, replay-v22/codec v20, Alembic 0017, Experiment BD

## Goal

Give agents a bounded way to infer what a foreign term probably means in their own vocabulary when two linguistic communities meet. No agent receives a dictionary, a translation table, or another owner's meaning. A listener builds an owner-scoped mapping from a foreign surface term to one or more of its own active terms, using evidence available through ordinary observation, delivered communication, teaching, artifacts, and context. The mapping records confidence and provenance and may remain partial, ambiguous, or wrong.

The engine never corrects a mapping and never turns one meaning into world state. Normal communicated-memory and belief formation may consume a translated interpretation, and normal social action may use a learned foreign term, so a mistranslation can propagate through testimony, belief revision, and interaction exactly as any other subjective error can. Detached analysis compares listener interpretations with the speaker's own selected referent to report cross-group communication accuracy, provenance, confidence, and influence without feeding any result back to agents.

Three layers stay separate:

- **Objective evidence:** delivered utterances, observed entities, observed artifacts, and their opaque IDs.
- **Subjective mapping:** the listener's owner-scoped hypothesis that foreign term X corresponds to own term Y, with confidence, alternatives, and provenance.
- **Analytical accuracy:** detached comparison against the speaker's own selected referent. It is an inter-subjective intent proxy, not objective truth and not an objective dictionary.

## Current Implementation Evidence

- **Foreign labels are currently absorbed without translation.** `src/agents/cognition/semantic_naming.py` `_apply_transmission` accepts a delivered `call` relation and records the foreign token as a new `LabelBinding` on the listener. The listener can therefore accumulate a foreign term, but there is no explicit mapping to an existing own term, no multi-target ambiguity, and no confidence/provenance dedicated to translation.
- **Symbolic interpretation requires literal own labels.** `src/agents/cognition/symbolic_language.py` `_apply_transmission` resolves composition parts only through the listener's active `TerminologyLedger`. A composition containing foreign parts becomes `partial` or `unresolved`; there is no translation-assisted resolution.
- **Naming and symbolic ledgers already have the right ownership boundaries.** `TerminologyLedger`, `SymbolicLedger`, `NamingEvidenceItem`, `SymbolicEvidenceItem`, sense history, runtime checkpoints, blank-slate exclusions, and runner result exports are owner-scoped and validated. Translation can reuse these patterns rather than introduce a new authority.
- **Contact and candidate communities already exist.** v3-24 adds neutral `ContactRecorded`, `runner-config-v45`, replay-v22/codec v20, and six contact families. v3-23 provides analysis-only `CandidateCommunityRow` values through `society_emergence`; `contact_lexical_borrowing@1` already measures cross-community naming evidence. Translation accuracy should reuse these detached communities and never expose them to cognition.
- **Communicated testimony already flows into beliefs.** `src/agents/cognition/communication.py` builds a fresh owner-scoped `MemoryTrace` from a delivered message; `src/agents/cognition/defaults.py` evaluates communicated testimony with trust and sender confidence. A bounded translated relation overlay can enter this existing path without a new belief store, trust rule, or world event.
- **Delivery and social actions are already structured.** `src/world/communications.py` bounds relations to subject/predicate/object atoms. `Talk`/`Ask`/`Tell` already carry structured content. Translation can use these atoms and must not add a new command or relation protocol.
- **Runtime carrying and export are established.** `AgentRuntimeCheckpoint` carries `semantic_naming` and `symbolic_language`; `SimulationRunnerResult` exports `terminology_ledgers`, `symbolic_ledgers`, and `initial_lifecycle_records`; `new_agent_initialization.py` excludes them from blank-slate bootstrap. Translation needs the same treatment.
- **Schema and counts are pinned.** `runner-config-v46` is the latest mode-only schema; 43 commands, 73 observer semantic types, 109 metric families, replay-v22/codec v20, and Alembic `0017`. `src/experiments/semantic_drift_scenario.py` (Experiment BC) is the latest V3 scenario.
- **Known gaps:** no translation ledger, no foreign-term-to-own-term mapping, no bounded ambiguity, no translation provenance channels, no translated symbolic parts, no translated testimony overlay, no outbound foreign-term selection, no translation metrics, and no cross-group accuracy family.

## Compatibility and Authority Contract

1. `WorldEngine` remains the sole objective mutation authority. This plan adds **no** world behavior: no new command, no new event, no new perception field, no new RNG stream, no new identifier namespace, no Alembic migration.
2. The closed `AgentCommand` count stays **43**. The observer semantic-type count stays **73**. Replay stays `EVENT_SCHEMA_REPLAY_V22`, persistence codec stays `v20`, `communication.v1` is unchanged, `/v1` and `observer-protocol-v1` are unchanged. Only the runner schema advances to `runner-config-v47` when translation is enabled.
3. No new capability flag. `translation_mode` is a per-agent cognition treatment, default `DISABLED`, lockstep between `simulation.runner_models.TranslationMode` and `agents.cognition.configuration.CognitionTranslationMode`. It requires deterministic `semantic_naming_mode`; symbolic language is optional.
4. `runner-config-v47` is a mode-only increment. It adds no root sibling. When contact/regions/public goods/collective projects are active it carries the same active v44/v45 family root keys; when they are absent it carries the prior highest-active root keys. v47 never implies contact, regions, public goods, cultural memory, or any other channel. Absent translation keeps the prior highest-active schema; the default write remains `runner-config-v4`.
5. A translation mapping is an owner-scoped hypothesis, never an objective dictionary. There is no shared mapping table, no global lexicon object, no world-owned translation, and no `correct` field in the agent ledger. An agent may hold several candidate targets for one foreign term.
6. `exact`, `partial`, `ambiguous`, and `wrong` are **analysis-only** classifications. They compare a listener mapping with the speaker's own selected referent as an intent proxy. They never assert objective truth and never flow back to cognition.
7. A listener never copies another owner's binding, composition, mapping, confidence, or hypothesis. Translation evidence may reference an actor/speaker ID and a delivered message, but the target is always the listener's own active binding. Translation is deterministic cognition over existing evidence; no LLM provider, prompt, external dictionary, or natural-language gloss is used. `multi_hop_testimony_tracking` remains fail-closed.
8. Mistranslation may influence beliefs and social interaction only through existing owner-scoped paths: translated relations may enter the listener's own communicated memory and normal testimony evaluation, and an agent may use a learned foreign term in an ordinary `Talk`/`Ask`/`Tell`. Normal trust, evidence, relationship, admission, and world-operation rules still apply. No translated value writes directly to a belief store or world state.
9. Analysis is detached and read-only. New analysis modules import no persistence, runtime, world private modules, or subjective ledger types; `src/experiments/composition.py` performs joins from detached rows. Metric documents and logs use opaque IDs and surface digests only; no raw label token, foreign token, message body, prompt, or narration enters a document or log.
10. Disabled/off behavior is byte-identical: no translation ledger, no mappings, no translated relations, no outbound rewrites, no observation fields, no RNG consumption, no trajectory changes.
11. Candidate communities are analysis-only. Agents never receive group membership, community labels, accuracy results, or another agent's mapping. Contact may expose the foreign term only through existing delivered communication, shared observation, or observed artifacts.
12. `src/` must not import `clients/`; no observer semantic type, Godot layout, or protocol name changes. A researcher-only translation overlay may expose digests and bands but must not expose raw tokens or objective authority.

## Design Decisions

### Per-agent mode and locked policy

- Create `src/agents/cognition/translation.py` with `TRANSLATION_POLICY_VERSION = "translation.v1"`.
- `TranslationMode` values are `disabled` and `deterministic`. `CognitionTranslationMode` mirrors it and requires `CognitionSemanticNamingMode.DETERMINISTIC`.
- Policy constants are locked in code and never serialized in runner JSON: active strength `0.45`, retire strength `0.15`, decay `0.04`, promotion count `3`, max mappings `16`, max targets per mapping `3`, max evidence `32`, max applications `32`, ambiguity margin `0.10`, outbound interval `4`, teaching window `8`.
- Evidence deltas are closed: shared observation `0.18`, demonstration `0.14`, repeated interaction `0.10`, teaching `0.20`, artifact `0.12`, context `0.06`.
- `runner-config-v47` carries only the per-agent mode. No weights, thresholds, dictionary entries, or language identifiers are configurable.

### Owner-scoped translation contracts

- `TranslationSourceKind` is closed: `label`.
- `TranslationMappingStatus` is closed: `candidate`, `active`, `retired`.
- `TranslationFit` is closed: `resolved`, `partial`, `ambiguous`, `unresolved`. It is the owner's structural self-assessment, never a correctness claim.
- `TranslationEvidenceChannel` is closed: `shared_observation`, `demonstration`, `repeated_interaction`, `teaching`, `artifact`, `context`.
- `TranslationApplicationKind` is closed: `symbolic_interpretation`, `outbound_term`.
- `TranslationApplicationOutcome` is closed: `applied`, `skipped`, `ambiguous`, `unresolved`.
- `TranslationStrengthBand` is closed: `candidate`, `low`, `mid`, `high`.
- `TranslationTarget` holds `binding_id`, `label_token`, `referent_kind`, and quantized `weight`. It must reference an own active `LabelBinding`; a target with another owner or a retired/merged binding rejects with a stable reason code.
- `TranslationEvidenceItem` holds `evidence_id`, `ordinal`, `channel`, `lineage_ref`, `tick`, optional `actor_id`, and the ordered `target_binding_ids` that the evidence supports. It never holds another owner's hypothesis or a free-form gloss.
- `TranslationApplication` holds `application_id`, `ordinal`, `tick`, `kind`, optional `message_id`, `mapping_id`, `outcome`, optional `target_binding_id`, and optional `actor_id`.
- `TranslationMapping` holds `mapping_id`, `owner_id`, `source_token`, `source_digest`, `source_kind`, ordered `targets`, `status`, `fit`, `strength`, `evidence_count`, `first_tick`, `last_tick`, `last_use_tick`, `usage_count`, bounded `evidence`, bounded `applications`, and bounded `notices`.
- `mapping_id` is an owner-scoped deterministic digest of `(owner_id, "translation", source_digest)`. The same foreign surface form heard by two owners is intentionally two different mappings. `source_digest` is SHA-256 of `translation|<source_token>` truncated to 16 hex chars; it is safe to compare across owners without exposing the token.
- `source_token` must match the existing label-token shape `^[a-z][a-z0-9_]{0,31}$`. Target `label_token` uses the same shape. A mapping cannot target its own source token, and the source token's own binding is never a valid target. A foreign token that already resolves to an active own binding is treated as known and does not create a translation mapping.
- `TranslationLedger` holds `owner_id`, at most 16 mappings, bounded notices, and the policy version. `empty_translation_ledger`, `require_owner_translation`, and deterministic id helpers mirror the naming/symbolic ownership guards.
- Constructors reject unknown enums, duplicate targets, duplicate evidence, duplicate applications, non-monotonic ordinals/ticks, foreign owners, cap overflows, invalid tokens, non-quantized confidence, and target bindings that do not match the supplied terminology ledger.

### Inference channels

`apply_translation_update(observation, identity, previous, terminology, symbolic=None, memories=(), advice_delta=(), mentorship=None, policy=None)` runs after the updated naming and symbolic ledgers exist. It never receives `WorldEvent` or another owner's ledger.

- **Shared observation:** when a delivered `call` relation uses a foreign token with referent kind K, and the listener observes at least one entity of kind K in the same observation, map the foreign token to each own active binding of kind K whose top candidate is one of those observed entities. Multiple matching own bindings produce multiple targets and therefore ambiguity; no match creates no mapping.
- **Demonstration:** when one delivered message contains a foreign token and an own active token whose `call` kinds agree, or a composition atom pairs a foreign part with an own part, add evidence for the own token. A message with two foreign tokens and no own token adds no demonstration evidence.
- **Repeated interaction:** when the same foreign token has been heard from the same speaker on at least two prior ticks and the listener has own active bindings of the same kind, add low-strength evidence. One matching own binding yields one target; several matching own bindings yield the top two by strength and a deterministic tie-break by binding id.
- **Teaching:** when `advice_delta` or an active mentorship bond identifies the speaker as a teacher and the delivered message uses a foreign token with a known referent kind, add high-strength evidence to own active bindings of that kind. The teaching window is at most 8 ticks. A teaching act is testimony about a mapping, not a dictionary entry.
- **Artifact:** when the listener observes an `ObservedArtifact` whose content relations contain `subject=foreign_token`, `predicate="call"`, and `object=kind`, add evidence to own active bindings of that kind. Artifact marks remain objective; the mapping is inferred by the listener. Artifacts never download meaning into memory automatically.
- **Context:** when no other channel fires for a foreign token in a delivered message and the listener has exactly one active own binding of the object kind at the current location/context, add low-strength context evidence. Context never overrides stronger evidence and never creates a mapping when the kind is unknown.

Promotion, ambiguity, and decay:

- A mapping becomes `active` when strength reaches `0.45` and evidence count reaches `3`; otherwise it stays `candidate`.
- If the top two target weights are within `0.10`, `fit=ambiguous`; if a target binding has multiple candidates or lacks a top candidate, `fit=partial`; if exactly one target has a top candidate and the margin is clear, `fit=resolved`; with no targets, `fit=unresolved`.
- Evidence that contradicts the current top target does not delete the old target. It updates target weights; alternatives remain bounded. A mapping is never silently rewritten to a single answer.
- Decay uses logical ticks only. Strength below `0.15` retires the mapping; retired mappings stay bounded and can be re-promoted by new evidence. No wall clock, no global RNG, no similarity merge.
- Disabled mode returns `None` and allocates nothing. A carried ledger from a disabled owner is cleared.

### Runtime carrying and blank-slate behavior

- `SubjectiveSnapshot`, `CognitiveLoopProposal`, `CognitiveLoopResult`, `AgentRuntimeCheckpoint`, and `SimulationRunnerResult` gain an optional `translation` / `translation_ledgers` field following the existing naming/symbolic pattern.
- To keep the fixed stage order and avoid a naming/symbolic cycle, `_prepare_translation` runs after the updated naming and symbolic ledgers. Translation-assisted symbolic interpretation and the communicated-memory overlay consume the carried previous-tick translation ledger; new mappings become effective for those paths on the next tick. Outbound selection uses the current-tick updated ledger.
- `AgentRuntimeState` gains `_translation`; the runtime commits after the cognitive loop and restores it from checkpoints alongside naming and symbolic ledgers.
- `perception.py` passes `translation` into `SubjectiveSnapshot`; it remains researcher-only and is never added to objective observer frames.
- `new_agent_initialization.py` adds `translation` to `SUBJECTIVE_COPY_DENY_LIST`, `BLANK_SLATE_SUBJECTIVE_STORES`, and `BlankSlateStoreCounts`. A new agent starts with an empty translation ledger and no inherited mappings.
- `runner.py` exports `translation_ledgers` in owner order and logs only ledger/mapping counts.

### Communicated memory, testimony, and beliefs

- Extend `build_communicated_memory_trace` with an optional `translation` ledger. When present and the mode is enabled, append at most four owner-local translated relations to the trace.
- For each delivered relation, if exactly one endpoint is a foreign token with an active, unambiguous mapping to the listener's own active binding, append a copy of the relation with that endpoint replaced by the target own label token. If both endpoints are foreign and both map unambiguously, append the fully translated relation. If a mapping is ambiguous or partial, append nothing for that relation and record no invention.
- The original relation is preserved. The translated relation is an interpretation, not a replacement; normal testimony evaluation, trust, confidence, contradiction, and belief revision remain authoritative for subjective belief updates.
- The overlay is capped at four translated relations per message and obeys the existing `MemoryTrace` caps. It does not add a new memory field, provenance field, belief store, or relationship rule. The message content fingerprint remains the speaker's content fingerprint.
- A wrong mapping can therefore support a wrong belief through the same communicated-evidence path as any other mistaken testimony. No analysis result corrects it and no world operation is bypassed.
- Disabled/off traces are byte-identical to today.

### Outbound foreign-term selection and social interaction

- Add `translation_communicate_utterance(command, owner_id, tick, observation, identity, translation, terminology, mode)` alongside the existing naming/symbolic utterance hooks.
- It runs after the symbolic utterance hook and only for an existing `Talk`, `Ask`, or `Tell`. If no active unambiguous mapping was learned from the current recipient, it returns the command unchanged.
- For at most two own label tokens in existing `call` relations, replace the target own token with the foreign source token learned from that recipient. Preserve recipient, declared transmission fields, concepts, and all other relations. Never choose a new recipient, mint a command kind, or add a relation.
- Selection is deterministic: active status, strength at or above the active threshold, recipient actor match, outbound interval, stable tie-break by `(strength, mapping_id)`. Usage increments `usage_count` and sets `last_use_tick`.
- A wrong mapping may make the agent use the wrong foreign term with the source speaker. The resulting misunderstanding is ordinary social interaction; no engine correction or shared dictionary is introduced.
- Ambiguous mappings are not used for outbound rewriting. They may still be resolved as ambiguous in analysis and may bias a future clarification design, but this plan adds no new ask/tell policy.

### Translation-assisted symbolic interpretation

- Add an optional `translation` parameter to `apply_symbolic_update` and `_apply_transmission` in `symbolic_language.py`; default `None` preserves current behavior exactly.
- For a composition part that is not an active own label, resolve it through the listener's translation ledger. Only active, unambiguous mappings are substituted. Ambiguous mappings produce a `partial` parse outcome and an `ambiguous_translation` notice; unresolved parts keep the existing `partial`/`unresolved` outcomes.
- The stored composition uses the listener's own label tokens. The message ID and structural parse outcome remain attached to the delivered message. A mistranslation can therefore create or reinforce a wrong owner-local composition, which may later be used in ordinary communication.
- No new `SymbolicParseOutcome` value, no new composition operator, no new command, and no change to `communication.v1`.

### Detached rows and digest policy

Create `src/analysis/translation_metrics.py` with frozen rows and validation:

- `TranslationMappingRow(owner_id, mapping_id, source_digest, source_kind, target_label_digests, target_referent_kinds, target_referent_digests, status, fit, strength_band, evidence_count, usage_count, channels, first_tick, last_tick)`
- `TranslationMessageRow(message_id, speaker_id, listener_id, tick, source_digest, source_kind, declared_confidence_band, speaker_referent_kind, speaker_referent_digest, listener_referent_kind, listener_referent_digest, outcome, mapping_id, interpretation_source, confidence_band, dominant_channel, cross_community)`
- `TranslationInfluenceRow(owner_id, mapping_id, message_id, source_digest, target_label_digest, effect_kind, outcome, tick, actor_digest, confidence_band)`
- `TranslationAnalysisInputs(mappings, messages, influences, communities, expected_owner_count)`

`TranslationOutcome` is closed for analysis: `exact`, `partial`, `ambiguous`, `wrong`, `unresolved`, `unresolved_intent`. `unresolved_intent` means the speaker's own selected referent could not be resolved from detached evidence; it is a coverage gap, never a zero or a wrong mapping. `TranslationInterpretationSource` is closed: `mapping`, `own_binding`, `none`. A same-surface-form term that the listener already owns is interpreted from `own_binding` even when no translation mapping exists, so a false friend is classified `wrong` rather than `unresolved`.

Digest rules:

- source term: SHA-256 of `translation|<source_token>` truncated to 16 hex chars;
- own term: SHA-256 of `label|<label_token>` truncated to 16 hex chars;
- referent: SHA-256 of `<referent_kind>|<referent_id>` truncated to 16 hex chars.

Rows never contain raw label tokens, foreign tokens, message bodies, prompts, or narration. Communities and generations are resolved at analysis time from detached candidate-community rows, never stored in the translation ledger.

### Metric families

- **`translation_learning@1`** — mapping inventory and provenance:
  - mapping count, active/candidate/retired counts, resolved/partial/ambiguous/unresolved fit counts, target count, multi-target mapping count, evidence count, usage count, channel counts for all six channels, confidence-band counts, first/last tick ranges, coverage.
  - Availability `absent` when no mapping exists. A run with only candidate mappings reports candidate counts, not fabricated active counts.
- **`cross_group_translation@1`** — cross-group communication accuracy:
  - delivered foreign-term message count, mapped/unmapped counts, mapping-versus-own-binding interpretation counts, exact/partial/ambiguous/wrong/unresolved counts and rates, `unresolved_intent` coverage, cross-community speaker-listener pair count, community pair count, dominant-channel accuracy counts, mean confidence for exact versus wrong mappings, and coverage.
  - Accuracy is computed only for cross-community pairs when candidate communities are available. If communities are absent, the family is `absent`, not zero. `exact` means the listener's top target resolves to the same kind and opaque referent as the speaker's own selected top candidate. `partial` means the speaker's referent appears among the listener's alternative targets but is not the unambiguous top. `ambiguous` means multiple eligible targets remain. `wrong` means a single resolved target points to a different kind or entity. These are descriptive intent-proxy labels.
- **`translation_influence@1`** — downstream subjective and social effects:
  - communicated-memory overlay count, translated relation count, symbolic interpretation application count, outbound foreign-term rewrite count, `Talk`/`Ask`/`Tell` rewrite mix, wrong-mapping influence count, ambiguous-skip count, affected owner count, and coverage. Influence rows are effect-tagged as `communicated_memory_overlay`, `symbolic_interpretation`, or `outbound_term`.
  - An influence row is descriptive association. The family never claims that a translation caused a belief or relationship change and never feeds the result back to cognition.
- Register `MetricFamilyId.TRANSLATION_LEARNING`, `CROSS_GROUP_TRANSLATION`, `TRANSLATION_INFLUENCE`; `METRIC_FAMILY_COUNT` moves 109 → 112.

### Experiment BD (off the V1 regression gate)

- New `src/experiments/translation_scenario.py`, experiment id `cross_cultural_translation@1`, catalog builder `experiment_bd_translation`.
- Arms:
  - `bd-off`: translation and naming disabled; no mappings, no overlays, all three families absent or empty by catalog convention.
  - `bd-naming-only`: naming deterministic, translation disabled; foreign terms are heard but no mapping is inferred.
  - `bd-shared-observation`: two region-separated populations with naming + translation and a journey/contact bridge; a listener observes a referent while hearing a foreign term.
  - `bd-demonstration`: diagnostic delivered message pairs a foreign token with the listener's own active token of the same kind.
  - `bd-repeated-teaching-artifact`: repeated cross-group messages, a teaching/advice relation, and a seeded observed artifact carrying a foreign `call` relation; covers the three non-shared channels without requiring a particular one to win.
  - `bd-ambiguous-wrong`: two own active bindings of the same kind and a diagnostic message that supports the wrong one; asserts ambiguity/wrong are representable and that no world truth correction or shared dictionary appears.
  - `bd-unsupported` non-run fixture: translation mode without deterministic naming rejects with the stable code.
- The arbiter asserts only structural facts: off arms emit no mappings or overlays; enabled arms have monotonic mapping ticks and bounded targets; isolated populations do not share mappings without a delivered/shared/artifact channel; translated relations appear only when the listener has an own target; ambiguous mappings are not forced to a single answer; wrong mappings are not corrected by the engine; no agent receives community labels or analysis results. It never asserts that translation, convergence, agreement, or accuracy "succeeded".
- Register `cross_cultural_translation@1` in `OFF_GATE_MATRIX_EXPERIMENT_IDS` and runtime dispatch, following BC.

### Presentation and documentation

- Add a researcher-only overlay, not an objective event: `GET /v1/simulations/{run_id}/observer/agents/{agent_id}/translation` returning digest-only mappings, targets, status, fit, confidence band, channel counts, and usage counts. It reads the owner runtime checkpoint and must not expose raw foreign tokens, message bodies, or another owner's mapping.
- Objective frames, `KNOWN_TYPES`, observer protocol, Godot layout, and semantic counts stay unchanged.
- Documentation: `docs/social-communication.md` (translation semantics, no dictionary, ambiguity/wrong, memory overlay), `docs/architecture.md` (v47, boundary, counts, unchanged replay/codec), `docs/configuration.md` (v47 and per-agent mode), `docs/persistence.md` and `docs/simulation-runner.md` (ledger export, unchanged replay/codec), `docs/analysis-metrics.md` (three families, 109 → 112), `docs/experiments.md` (Experiment BD and arms), `docs/research-api.md` (researcher overlay), `docs/development.md` (verification block), and `README.md` index if a new page is added.

## Commit Plan

Commit messages are suggestions for implementation; this planning command creates no commits.

- **Commit 1** (tasks 1–2): `feat(v3): add translation contracts and runner-config-v47`
- **Commit 2** (tasks 3–5): `feat(v3): carry and learn owner-scoped translation mappings`
- **Commit 3** (tasks 6–8): `feat(v3): apply translated testimony, social terms, and symbolic parts`
- **Commit 4** (tasks 9–12): `feat(v3): add detached translation learning, accuracy, and influence metrics`
- **Commit 5** (tasks 13–14): `feat(v3): add Experiment BD and translation research overlay`
- **Commit 6** (tasks 15–16): `docs(v3): document translation and reconcile compatibility gates`

## Tasks

### Phase 1 — Contracts and configuration

- [x] **Task 1: Define the owner-scoped translation contract with exact validation.**
  - Files: create `src/agents/cognition/translation.py`; update `src/agents/cognition/__init__.py`; create `tests/unit/test_translation_contracts.py`.
  - Deliver `TRANSLATION_POLICY_VERSION`, `TranslationMode`, `TranslationSourceKind`, `TranslationMappingStatus`, `TranslationFit`, `TranslationEvidenceChannel`, `TranslationApplicationKind`, `TranslationApplicationOutcome`, `TranslationStrengthBand`, `TranslationTarget`, `TranslationEvidenceItem`, `TranslationApplication`, `TranslationMapping`, `TranslationLedger`, `TranslationPolicy`, `default_translation_policy`, `empty_translation_ledger`, `require_owner_translation`, `translation_mapping_id`, `translation_source_digest`, and `translation_strength_band`.
  - Enforce owner consistency, target binding ownership/status, closed enums, token shape, source-digest consistency, unique targets, unique evidence/applications, ordinal and tick monotonicity, caps (16 mappings, 3 targets, 32 evidence, 32 applications), and quantized confidence. Reject foreign ledgers, analysis rows, free-form glosses, embedded dictionaries, and target tokens equal to the source token.
  - Mapping construction and update accept the owner `TerminologyLedger` as validation context: every target must resolve to an own active binding, every `TranslationEvidenceItem.target_binding_ids` entry must be a subset of that mapping's targets, and every `TranslationApplication.mapping_id` must equal the containing mapping. A target cannot be validated in isolation.
  - Acceptance: frozen contracts round-trip; caller mutation cannot alter them; an ambiguous mapping with two targets is legal; a mapping with no target is `unresolved`; an incorrect target is representable without a `correct` flag; disabled mode allocates no ledger.
  - Logging: DEBUG at construction boundaries with counts and safe reason codes only; INFO once per ledger with mapping/status counts. Never log source tokens, target tokens, referent IDs, or evidence payloads.
  - Dependencies: none.

- [x] **Task 2: Gate and serialize `runner-config-v47`.**
  - Files: `src/simulation/runner_models.py`, `runner_serialization.py`, `compatibility.py`, `src/agents/cognition/configuration.py`, `src/experiments/matrix_schema.py`, `src/simulation/__init__.py`; create `tests/unit/test_runner_config_v47.py`; update `tests/unit/test_runner_config_v46.py`, `tests/unit/test_compatibility_matrix.py`, `tests/unit/test_v3_flag_defaults.py`, matrix schema tests.
  - Add `TranslationMode` lockstep with `CognitionTranslationMode`. Add `translation_mode` to `AgentCognitionSpec`; add the lockstep `CognitionTranslationMode`, `translation_mode`, and `translation_policy` fields to `CognitionLoopConfig`; default `DISABLED`.
  - Add `RUNNER_SCHEMA_VERSION_V47 = "runner-config-v47"`, `_COGNITION_KEYS_V47 = {*_COGNITION_KEYS_V46, "translation_mode"}`, and `_v47_family_root_keys` based on the active v44/v45/v46 family roots with no new root sibling. Sweep every schema set/list/allowlist that currently includes v46 so v47 is legal, including `SUPPORTED_RUNNER_SCHEMA_VERSIONS`, `_COGNITION_SCHEMA_CONSOLIDATION`, skill/artifact/regional/contact/collective/public-good/migration sets, serialization encode/decode branches, and `matrix_schema.finalize_matrix_cell_config`.
  - Gates: deterministic `translation_mode` requires `runner-config-v47` (`translation_requires_v47`); deterministic translation requires deterministic semantic naming (`translation_requires_semantic_naming`); v47 requires at least one deterministic translation mode (`v47_requires_translation`). v47 accepts contact/regions/public goods/collective projects and symbolic language, but implies none of them. v46 remains valid for symbolic-only runs. Unknown/null nested keys reject.
  - Highest-wins order in `finalize_matrix_cell_config` is explicit: translation > symbolic language > cultural contact > regions/migration > public goods > collective projects > resource exchange > subjective valuation > structured commitments > possession succession > technique lifecycle > bounded experimentation > knowledge genealogy > … . Translation-on emits v47 with or without symbolic mode; symbolic-only remains v46.
  - Acceptance: v1–v46 keysets and selectors unchanged; v47 round-trips with and without contact/regions/symbolic mode; v47 never implies a root sibling; default write stays v4; v47 on pre-v47 and translation-on without naming fail closed; matrix finalize selects v47 only when translation is on.
  - Logging: INFO at activation with schema and mode; DEBUG gate decisions; WARN invalid combinations with safe codes only. No config dumps, tokens, or referent IDs.
  - Dependencies: 1.

- [x] **Task 3: Carry and export the translation ledger through runtime, checkpoints, and runner results.**
  - Files: `src/agents/cognition/models.py`, `src/simulation/perception.py`, `src/simulation/run_control.py`, `src/simulation/agent_runtime.py`, `src/simulation/runner_models.py`, `src/simulation/runner.py`, `src/simulation/new_agent_initialization.py`, `src/agents/cognition/configuration.py`; create `tests/unit/test_translation_runtime_carry.py`, `tests/unit/test_translation_blank_slate.py`; update checkpoint/runtime tests.
  - Add `translation` to `SubjectiveSnapshot`, `CognitiveLoopProposal`, `CognitiveLoopResult`, and the owner guards. Add `translation` to `AgentRuntimeCheckpoint`, `AgentRuntimeState`, commit/restore paths, `build_perspective`, and `SimulationRunnerResult.translation_ledgers`.
  - Export owner-ordered translation ledgers from `runner.py`; skip `None`; preserve owner order; do not mutate ledgers. Add `translation` to the blank-slate deny list, blank-slate stores, and `BlankSlateStoreCounts`.
  - Acceptance: enabled runs expose one ledger per owner in deterministic order; disabled runs expose empty tuples; restore/fork preserve ledgers and live/restored parity; new agents start with an empty ledger; result/event/replay/codec documents are unchanged; disabled behavior is byte-identical.
  - Logging: INFO once at export with ledger/mapping counts; DEBUG per-owner mode and mapping count. Never log source tokens, target tokens, referent IDs, or evidence.
  - Dependencies: 1, 2.

### Phase 2 — Learning, testimony, and interaction

- [x] **Task 4: Implement channel inference, promotion, ambiguity, and decay.**
  - Files: `src/agents/cognition/translation.py`, `src/agents/cognition/__init__.py`; create `tests/unit/test_translation_learning.py`, `tests/unit/test_translation_channels.py`.
  - Deliver `apply_translation_update`, `resolve_translation_token`, `translation_targets_for_kind`, and bounded helpers. Implement the six channels exactly as described above, with deduplication by `(channel, lineage_ref, tick, actor_id, target_binding_id)`.
  - Shared observation uses only the listener's current `Observation`; demonstration uses co-occurring foreign/own `call` atoms or composition parts; repeated interaction uses at least two prior events from the same speaker; teaching uses `advice_delta`/mentorship and an 8-tick window; artifact uses observed `ObservedArtifact` relations; context is a low-strength fallback only when no other channel fires.
  - Enforce promotion at strength `0.45` and evidence count `3`, ambiguity margin `0.10`, partial fit for missing/multiple target candidates, retirement below `0.15`, 16-mapping cap, 3-target cap, and 32-evidence cap. Validate every new or changed target against the supplied `TerminologyLedger`; reject foreign-owner, retired, merged, or dangling target bindings. Never copy another owner's hypothesis, confidence, or ledger.
  - Acceptance: one shared-observation episode creates a candidate mapping; three consistent observations promote it; two close targets produce `ambiguous`; a single target with multiple own candidates produces `partial`; an incorrect target is stored without correction and may later be classified `wrong` only in analysis; teaching/artifact/repeated/context each produce their closed channel; disabled mode and empty evidence create no mapping; a foreign token with no own binding stays unresolved.
  - Logging: DEBUG per channel with counts and mapping status only; INFO once per updated ledger with mapping/status/ambiguity counts. Never log tokens, referent IDs, or message content.
  - Dependencies: 3.

- [x] **Task 5: Wire translation into the cognitive loop and deliberation.**
  - Files: `src/agents/cognition/loop.py`, `src/agents/cognition/configuration.py`, `src/agents/cognition/models.py`, `src/simulation/runner.py`, `src/simulation/agent_runtime.py`; create `tests/unit/test_translation_loop.py`; update configuration/runner tests.
  - Add `_prepare_translation` after naming, symbolic, and mentorship/advice preparation. Pass the carried ledger from `SubjectiveSnapshot`, the updated naming and symbolic ledgers, `advice_delta`, and mentorship. Return `None` when disabled or when naming is unavailable; log a safe `constituent_missing` warning. Symbolic interpretation receives the carried previous-tick translation ledger; the current-tick update is used for deliberation and the next tick's symbolic/memory paths.
  - Add `TranslationPolicy` construction to `CognitiveLoop` and `CognitionLoopConfig`; add `_translation_mode` / `_translation_policy` to `CognitiveLoop.__slots__` and constructor fields; map `TranslationMode`/`CognitionTranslationMode`; pass the ledger to deliberation for outbound selection. Include `translation` in the loop result.
  - Add `translation_mode` and `translation_policy_version` to `CognitionLoopConfig.condition_fingerprint_material` so translation-on and translation-off runs cannot share a cognition fingerprint.
  - Acceptance: enabled runs carry one ledger per owner; disabled runs allocate nothing; translation updates are deterministic for identical observations; translation cannot run without naming; no mutation of naming or symbolic ledgers; no new stage, no new component, no RNG.
  - Logging: INFO at mode activation; DEBUG per tick with mapping count and channel counts only. Never log tokens, referent IDs, or message content.
  - Dependencies: 4.

- [x] **Task 6: Translate communicated memory and testify through existing belief paths.**
  - Files: `src/agents/cognition/communication.py`; create `tests/unit/test_translation_communicated_memory.py`, `tests/unit/test_translation_belief_influence.py`. Do **not** modify `src/agents/cognition/defaults.py` or `src/memory/belief_formation.py`: `extract_evidence_candidates` already turns memory relations into `experienced_concept` and relation claims, so translated relations enter belief formation through the existing path.
  - Extend `build_communicated_memory_trace` with an optional translation ledger and append at most four translated relations per delivered message. Translate only endpoints with an active, unambiguous mapping; preserve the original relation; when both endpoints map, translate both; when ambiguous or partial, append nothing for that relation.
  - The overlay must remain owner-scoped and must not add a memory field, provenance field, belief store, relationship rule, or world event. It enters normal communicated-memory formation and normal trust/testimony/contradiction evaluation. A wrong mapping may support a wrong belief through that path; no engine correction occurs.
  - Acceptance: disabled runs produce byte-identical traces; enabled runs append bounded translated relations; ambiguous mappings append nothing; a wrong mapping can alter the evidence available to belief formation without changing the original message or world state; a translated relation produces the expected `experienced_concept` and relation belief candidate through the unchanged `extract_evidence_candidates` path; trace and belief-candidate caps remain valid; no raw tokens appear in logs or metric documents.
  - Logging: DEBUG at overlay application with relation count, owner id, tick, and outcome band only; WARN on ambiguous/partial skips with safe codes. Never log relation text, tokens, or belief content.
  - Dependencies: 3, 4, 5.

- [x] **Task 7: Add outbound foreign-term selection.**
  - Files: `src/agents/cognition/translation.py`, `src/agents/cognition/deliberation.py`, `src/agents/cognition/loop.py`; create `tests/unit/test_translation_outbound.py`, `tests/unit/test_translation_social_interaction.py`.
  - Deliver `translation_communicate_utterance` and `translation_usage_update`. After the naming and symbolic utterance hooks, rewrite at most two own label tokens in existing `call` relations to the foreign source tokens learned from the current recipient. Preserve recipient, declared transmission, concepts, and all other relations. Record one bounded `outbound_term` application row per rewrite.
  - Require active, unambiguous mapping, recipient actor match, strength at or above the active threshold, and the outbound interval. Never choose a new recipient, mint a command kind, add a relation, or use an ambiguous mapping. Increment `usage_count` and set `last_use_tick`.
  - Acceptance: an agent speaks its own term when no recipient-matched mapping exists; it uses the foreign term only with the source recipient; ambiguous mappings never rewrite; usage is bounded; disabled mode returns the command unchanged; a wrong mapping can produce a wrong term in ordinary social interaction without any engine correction.
  - Logging: DEBUG at selection with owner id, tick, recipient id, mapping status, and rewrite count only; INFO once per update with aggregate counts. Never log tokens or utterance content.
  - Dependencies: 3, 4, 5.

- [x] **Task 8: Translate foreign parts inside symbolic interpretation.**
  - Files: `src/agents/cognition/symbolic_language.py`, `src/agents/cognition/loop.py`; create `tests/unit/test_translation_symbolic.py`; update symbolic transmission tests.
  - Add optional `translation` to `apply_symbolic_update` and `_apply_transmission`; the loop passes the carried previous-tick ledger. For a composition part that is not an active own label, substitute an active unambiguous target own label. Ambiguous mappings yield `partial` plus an `ambiguous_translation` notice; unresolved parts keep the existing outcomes.
  - Store the composition under the listener's own label tokens and preserve the delivered message ID. Record one bounded `symbolic_interpretation` application row per resolved or ambiguous part. Do not add a `SymbolicParseOutcome` value, operator, command, or protocol change.
  - Acceptance: without translation, symbolic behavior is byte-identical; with translation, a foreign composition can be parsed into an own composition; ambiguous mappings do not invent a composition; wrong mappings can create a wrong own composition; no cross-owner hypothesis is copied.
  - Logging: DEBUG with resolved/ambiguous/unresolved part counts and owner id only; no tokens, parts, or message content.
  - Dependencies: 4, 5.

### Phase 3 — Detached analysis and metrics

- [x] **Task 9: Define translation analysis rows and harvest them.**
  - Files: create `src/analysis/translation_metrics.py` (row DTOs, digest helpers, validation, outcome classification); update `src/analysis/__init__.py`, `src/experiments/composition.py`, `src/experiments/collectors.py`, `src/analysis/metric_service.py`, `src/analysis/models.py`, `src/experiments/metric_collection.py`; create `tests/unit/test_translation_rows.py`.
  - Deliver `TranslationMappingRow`, `TranslationMessageRow`, `TranslationInfluenceRow`, `TranslationAnalysisInputs`, `TranslationInterpretationSource`, `TranslationOutcome`, `translation_source_digest`, `translation_label_digest`, `translation_referent_digest`, `translation_mapping_rows_from_ledgers`, `translation_message_rows_from_events`, `translation_influence_rows_from_ledgers`, and `translation_analysis_inputs_from_harvest`.
  - Harvest translation ledgers from `arm` or `arm.runner_result`; harvest naming ledgers for speaker-intent resolution; harvest `Talked`/`Asked`/`Told` events for delivered foreign terms; reuse candidate-community rows and generation maps only when present. Move the harvest outside the regional/events branch so translation-only runs still produce learning metrics.
  - Resolve speaker intent from the speaker's own active binding top candidate for `(source_token, referent_kind)`. Resolve listener interpretation from an active mapping target first; if no mapping exists and the source token already resolves to the listener's own active binding, use that binding with `interpretation_source=own_binding` so a same-surface false friend can be classified `wrong`; otherwise `interpretation_source=none`. Missing speaker intent yields `unresolved_intent` and a coverage gap, never `wrong` or zero. Cross-community eligibility requires two distinct candidate communities.
  - Acceptance: rows round-trip; raw tokens never appear; the same surface form has the same digest across owners; owner-scoped mapping IDs stay owner-scoped; ambiguous mappings are not collapsed; a same-form term with no mapping resolves to `own_binding` and can be classified `wrong`; communities are optional; identical inputs produce identical ordering/fingerprints; no analysis module imports ledger types or persistence.
  - Logging: DEBUG with row/coverage counts and source counts; INFO once per harvest. Never log tokens, referents, or message bodies.
  - Dependencies: 3, 4, 5.

- [x] **Task 10: Implement `translation_learning@1`.**
  - Files: `src/analysis/translation_metrics.py`, `src/analysis/specifications.py`; create `tests/unit/test_translation_learning_metrics.py`.
  - Compute mapping inventory, status/fit counts, target counts, multi-target count, evidence/usage counts, six channel counts, confidence-band counts, tick ranges, and coverage. A mapping with no evidence is not fabricated; candidate mappings are reported as candidates.
  - Acceptance: zero mappings yield `absent`; a candidate-only run reports zero active and the correct candidate count; ambiguity is counted, not resolved; identical inputs produce identical documents; no raw tokens or referent IDs appear.
  - Logging: INFO at assembly with family id and availability; DEBUG with aggregate counts only.
  - Dependencies: 9.

- [x] **Task 11: Implement `cross_group_translation@1`.**
  - Files: `src/analysis/translation_metrics.py`, `src/analysis/specifications.py`; create `tests/unit/test_cross_group_translation_metrics.py`.
  - Compute delivered foreign-term counts, mapped/unmapped counts, exact/partial/ambiguous/wrong/unresolved rates, `unresolved_intent` coverage, mapping-versus-own-binding interpretation counts, cross-community pairs, dominant-channel accuracy, and mean confidence for exact versus wrong. Use only detached rows and candidate communities.
  - Classification: exact = same kind and same opaque referent as the speaker's selected top candidate; partial = speaker referent among alternative targets but not the unambiguous top; ambiguous = multiple eligible targets; wrong = a resolved target, including a same-form `own_binding` interpretation, points to a different kind or entity; unresolved = no active mapping and no own binding; unresolved_intent = speaker intent unavailable.
  - Accuracy denominator is `exact+partial+ambiguous+wrong`; `unresolved` and `unresolved_intent` are coverage gaps, never zeros. Confidence calibration compares mean mapping confidence for exact versus wrong outcomes and reports `None` when either denominator is zero.
  - Acceptance: absent communities yield `absent`, not zero; one community yields no cross-group pair and `absent`/coverage as defined; a wrong mapping is counted without correction; a same-form `own_binding` false friend is classified `wrong`, not `unresolved`; ambiguous is not counted as exact or wrong; missing speaker intent is a coverage gap; the accuracy denominator excludes `unresolved`/`unresolved_intent`; confidence means are `None` when denominators are zero; identical inputs produce identical documents.
  - Logging: INFO at assembly with availability, pair count, and community count; DEBUG with aggregate outcome counts only. Never log tokens or referents.
  - Dependencies: 9.

- [x] **Task 12: Implement `translation_influence@1` and register all three families.**
  - Files: `src/analysis/translation_metrics.py`, `src/analysis/specifications.py` (`METRIC_FAMILY_COUNT` 109 → 112), `src/analysis/metric_service.py`, `src/analysis/__init__.py`, `src/analysis/serialization.py`, `src/experiments/metric_collection.py`; create `tests/unit/test_translation_influence_metrics.py`; update every unit test that pins `METRIC_FAMILY_COUNT == 109`.
  - Compute communicated-memory overlays, translated relation count, symbolic interpretation applications, outbound rewrites, `Talk`/`Ask`/`Tell` rewrite mix, wrong-mapping influence count, ambiguous-skip count, affected owners, and coverage. Derive memory-overlay influence rows from delivered messages plus active mappings; read symbolic/outbound application rows from the translation ledger.
  - Influence cardinality is one row per mapping application. A translated relation with two translated endpoints yields two rows sharing the message ID and relation ordinal; symbolic interpretation with two mapped parts yields two `symbolic_interpretation` rows. Never count a relation once and its two mappings twice in the same denominator.
  - Add `TRANSLATION_LEARNING`, `CROSS_GROUP_TRANSLATION`, `TRANSLATION_INFLUENCE` specs with evidence inputs, denominators, zero-holding policy, and value keys. Add assembly branches behind the existing `_safe` wrapper.
  - Acceptance: catalog validation passes at 112; all three specs are discoverable; flags-off runs remain green and omit or mark families absent; metric documents expose only digests/bands/counts; no unsupported family is accepted by serialization; influence is descriptive and never causal.
  - Logging: INFO at assembly with each family id and availability; WARN on absent/degraded inputs with safe codes only.
  - Dependencies: 9, 10, 11.

### Phase 4 — Experiment, presentation, and documentation

- [x] **Task 13: Add Experiment BD and dispatch.**
  - Files: create `src/experiments/translation_scenario.py`; update `src/experiments/catalog.py`, `src/experiments/__init__.py`, `src/experiments/coordinator.py`, `src/experiments/matrix_runner.py`; create `tests/unit/test_experiment_bd.py`; update off-gate matrix tests.
  - Implement `cross_cultural_translation@1` with `bd-off`, `bd-naming-only`, `bd-shared-observation`, `bd-demonstration`, `bd-repeated-teaching-artifact`, `bd-ambiguous-wrong`, and the `bd-unsupported` config fixture. Reuse `_scenario`/`_regions` from the multiple-societies scenario and existing naming/symbolic/contact modes.
  - The diagnostic arms may use explicit commands to exercise the analytic contract; at least one arm remains cognition-driven through normal perception and deliberation. The shared/artifact/teaching arms use owned contact, journey, communication, teaching, and scheduled-artifact channels. The wrong arm must not add an objective correction.
  - The `bd-shared-observation` arbiter schedules journey arrival before the observation/talk window, keeps the listener and speaker co-located at the referent, and asserts co-presence plus a delivered foreign term in the same tick. A journey alone is not sufficient evidence of shared observation.
  - Arbiter: off arms have no mappings/overlays; enabled arms have bounded monotonic mappings; isolated populations do not share mappings without a delivered/shared/artifact channel; ambiguous mappings are not forced to one target; wrong mappings remain wrong in analysis and are not corrected; no agent receives community labels or analysis results; unsupported config fails closed with the stable code.
  - Acceptance: all arms run under the same seed/scenario identity where applicable; deterministic results across runs; catalog/count assertions updated; no arm claims forced accuracy, convergence, or a correct dictionary.
  - Logging: INFO at scenario build/arbitration with arm id and aggregate counts; DEBUG with safe structural details only. Never log tokens, referent IDs, or message bodies.
  - Dependencies: 3, 4, 5, 12.

- [x] **Task 14: Add the researcher-only translation overlay.**
  - Files: `src/observer/labels.py`, `src/api/observer_schemas.py`, `src/api/routes/observer.py`; create `tests/unit/test_translation_overlay.py`, `tests/unit/test_translation_route.py`.
  - Add `TranslationOverlay`/`TranslationMappingReading` and `project_translation_overlay` using digests, target digests, status, fit, strength band, channel counts, usage count, and tick range. Add `ObserverTranslationOverlayOut` and `GET /v1/simulations/{run_id}/observer/agents/{agent_id}/translation`.
  - The overlay schema exposes only source digest, target label digests, referent kinds/digests, status, fit, strength band, channel counts, usage count, and tick range. Raw foreign tokens, target tokens, message bodies, and foreign referent IDs are not fields.
  - The endpoint reads the owner checkpoint and returns only the researcher overlay. It must not expose raw foreign tokens, target tokens, message bodies, or another owner's mapping. Objective frames, `KNOWN_TYPES`, semantic counts, protocol, and Godot layout remain unchanged.
  - Acceptance: overlay round-trips; count matches mappings; disabled owners return an empty overlay; route is not part of objective frames; no token text appears in JSON; existing observer tests and semantic count pins remain green.
  - Logging: INFO at route completion with run id, agent id, mapping count, and duration only; WARN on unavailable checkpoint with a safe code. Never log tokens or mapping targets.
  - Dependencies: 3, 4, 5.

- [x] **Task 15: Update documentation and compatibility notes.**
  - Files: `docs/social-communication.md`, `docs/architecture.md`, `docs/configuration.md`, `docs/persistence.md`, `docs/simulation-runner.md`, `docs/analysis-metrics.md`, `docs/experiments.md`, `docs/research-api.md`, `docs/development.md`, `README.md` (index if needed).
  - Document the owner-scoped mapping contract, all six channels, confidence/provenance, exact/partial/ambiguous/wrong as analysis-only, no objective dictionary, translated testimony overlay, outbound foreign-term selection, runner-config-v47 and its exact gates, unchanged replay-v22/codec v20/Alembic `0017`/43 commands/73 observer semantic types, Experiment BD arms, and the three metric families at 109 → 112.
  - Acceptance: docs match code selectors; no stale claim of a new command, event, observer semantic type, capability flag, or replay/codec pair; all internal links resolve; no convergence, correctness, or causal-influence claim; examples are metadata-only.
  - Logging: not applicable to docs; examples must not include raw tokens or message bodies.
  - Dependencies: 12, 13, 14.

### Phase 5 — Verification

- [x] **Task 16: Reconcile architecture, compatibility, and full verification gates.**
  - Files: tests and any narrowly required wiring discovered by verification; do not weaken gates. Update `tests/architecture/` isolation/import tests, all count pins, compatibility tests, matrix schema tests, and the V1/V2/V3 flags-off suite.
  - Verify: focused translation suites; `uv run --frozen --python 3.12.14 pytest`; Ruff; mypy; import-linter; architecture isolation; the required V1/V2 compatibility gate; the V3 flags-off scientific-invariant gate; Experiment BD focused suite; Experiment BC/BB/BA regressions; matrix schema finalize.
  - Confirm Alembic head stays `0017`, replay/codec pair stays `v22`/`v20`, command count stays 43, observer semantic count stays 73, metric family count is 112, and runner schema v47 is the only new accepted schema. Confirm disabled runs are byte-identical and no raw tokens, referents, or message bodies enter logs or metrics.
  - Acceptance: no new gate exclusions or suppressed errors; translation mappings are bounded and monotonic; ambiguity/wrong are representable and uncorrected; translated overlays obey memory caps; outbound rewrites preserve command shape; analysis is detached and metadata-only; all three families are registered and tested.
  - Logging: record verification outcomes and safe failure codes in the plan log; never paste tokens, referent IDs, message bodies, prompts, or content.
  - Dependencies: 1–15.

## Verification Notes

- Focused suites to add or run during implementation:
  - `tests/unit/test_translation_contracts.py`
  - `tests/unit/test_runner_config_v47.py`
  - `tests/unit/test_translation_runtime_carry.py`
  - `tests/unit/test_translation_blank_slate.py`
  - `tests/unit/test_translation_learning.py`
  - `tests/unit/test_translation_channels.py`
  - `tests/unit/test_translation_loop.py`
  - `tests/unit/test_translation_communicated_memory.py`
  - `tests/unit/test_translation_belief_influence.py`
  - `tests/unit/test_translation_outbound.py`
  - `tests/unit/test_translation_social_interaction.py`
  - `tests/unit/test_translation_symbolic.py`
  - `tests/unit/test_translation_rows.py`
  - `tests/unit/test_translation_learning_metrics.py`
  - `tests/unit/test_cross_group_translation_metrics.py`
  - `tests/unit/test_translation_influence_metrics.py`
  - `tests/unit/test_experiment_bd.py`
  - `tests/unit/test_translation_overlay.py`
  - `tests/unit/test_translation_route.py`
- Required repository gates: default pytest, Ruff, mypy, import-linter, architecture isolation, V1/V2 compatibility, V3 flags-off invariants, matrix schema finalize, and BC/BB/BA regressions. No Godot suite is required because no observer semantic type, router entry, layout, or protocol shape changes.
- Manual reviewer checks: confirm no objective dictionary or shared mapping store exists; confirm a listener cannot copy another owner's mapping/confidence; confirm ambiguous and wrong mappings are legal and uncorrected; confirm translated relations enter only the listener's own memory; confirm outbound rewriting preserves recipient and command shape; confirm disabled runs allocate nothing and consume no RNG; confirm communities and accuracy are analysis-only; confirm logs and metric documents contain no raw tokens, referent IDs, or message bodies.
