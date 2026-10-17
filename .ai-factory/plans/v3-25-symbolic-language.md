# Implementation Plan: V3-25 Symbolic Language

Branch: main (current branch; `git.create_branches: false`)
Created: 2026-10-17
Mode: full (ultra depth requested)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes — mandatory `/aif-docs` checkpoint during implementation.
- Artifact naming: every plan artifact produced for this feature begins `v3-`; canonical file is `.ai-factory/plans/v3-25-symbolic-language.md`.
- Implementation scope: an optional, per-agent, owner-scoped compositional symbolic layer over the existing V2 semantic-naming ledger. Agents may combine two already-active private labels into a bounded binary composition, use that composition in ordinary `Talk`/`Ask`/`Tell` relations, and form their own listener-side interpretation. **No unrestricted natural-language invention, no grammar induction, no shared lexicon authority, no new command, no new objective event, no new capability flag, no natural-language model dependency.**

## Roadmap Linkage
Milestone: "M7 — V3 Generational Civilization"
Rationale: Extends the owned cultural/historical substrate from private naming into bounded compositional symbolic communication while preserving WorldEngine authority, owner-scoped meaning, and analysis-only social distribution.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] full mode confirmed; git.create_branches=false; resolved plan file: .ai-factory/plans/v3-25-symbolic-language.md (format=slug)
INFO [aif-plan] plan_default_milestone=auto surfaces M6 first; explicit V3 scope uses M7, following v3-22/v3-23/v3-24 precedent; this plan does not close M6
INFO [aif-plan] ultra request treated as full-mode depth; this skill has no separate ultra mode
INFO [aif-plan] RESEARCH.md absent and skill-context/aif-plan/SKILL.md contains context-budget rules only; research_influenced_plan=false
INFO [aif-plan] baseline selectors to recheck before implementation: 43 commands, 73 observer semantic types, 103 metric families, runner-config-v45, replay-v22/codec v20, Alembic 0017, latest Experiment BA

## Goal

Give agents a bounded way to combine symbols they already use into simple structured messages, and let researchers ask after the run how those compositions arose, how they were used between a speaker and a listener, how confident each owner was, and how they were distributed across populations. The layer must keep three things separate: the objective entity, the owner's subjective meaning, and any socially shared pattern. Different populations may therefore develop different vocabularies and different composition habits without any global lexicon, and contact may produce borrowing only through ordinary delivered communication.

## Current Implementation Evidence

- **V2 semantic naming already provides the substrate.** `src/agents/cognition/semantic_naming.py` owns `TerminologyLedger`, `LabelBinding`, `NamingCandidate`, `NamingEvidenceItem`, `NamingUtterancePlan`, `NamingReferentKind`, `NamingStatus`, and the locked `semantic-naming.v1` policy. `apply_naming_update` consumes one owner's `Observation`, `OwnerSafeSocialIdentity`, memories, and an optional `NamingCueSummary`; it is owner-scoped and rejects sibling ledgers and world authority (`_reject_forbidden`, L76-101, L1828-1904).
- **Transmission is already structured and bounded.** `naming_communicate_utterance` (L1995-2065) stamps one `call` relation onto an existing `Talk`; `_apply_transmission` (L1381-1442) accepts only `predicate == "call"` and parses `object` as a referent kind. `LabelBinding` caps are 16 bindings, 32 evidence items, 4 candidates, and 4 competitors.
- **Communication payloads are already generic enough for composition.** `src/world/communications.py` defines bounded `CommunicationRelation(subject, predicate, object)`, `CommunicationContent` (max 32 concepts, 32 relations), and `StructuredUtterance`. `predicate` is bounded text; closed semantics are imposed by consumers, not by the world. `Talk`/`Ask`/`Tell` all carry the same payload (`src/world/actions.py` L130-186).
- **Naming evidence is carried through runtime checkpoints.** `src/simulation/run_control.py` exposes `AgentRuntimeCheckpoint.semantic_naming`; `src/simulation/agent_runtime.py` commits and restores it; `src/simulation/perception.py` passes it into cognition; `src/simulation/new_agent_initialization.py` excludes it from blank-slate bootstrap.
- **Detached analysis already consumes naming evidence.** `src/analysis/semantic_naming_metrics.py` computes `emergent_semantic_naming@1` and persistence; `src/analysis/contact_lexical_borrowing.py` consumes metadata-only `ContactNamingEvidenceRow` rows; `src/experiments/composition.py` builds detached naming rows from ledgers; `src/analysis/metric_service.py` assembles cultural and contact families.
- **Population and contact context exists.** v3-23 adds analysis-only candidate communities (`society_emergence`, `society_divergence`, `society_isolation`); v3-24 adds `runner-config-v45`, replay-v22/codec v20, `ContactRecorded`, and `contact_lexical_borrowing@1`. Composition distribution must reuse those detached community rows rather than inventing a population authority.
- **Researcher presentation already exposes private labels.** `GET /{run_id}/observer/agents/{agent_id}/labels` reads the owner checkpoint and returns a researcher-only overlay; objective frames reject `semantic_naming`/`labels` (`src/observer/contracts.py`, `src/api/observer_schemas.py`).
- **Baseline:** 43 command variants, 73 observer semantic types, 103 metric families, `runner-config-v45`, replay-v22/codec v20, Alembic `0017`, latest Experiment BA. Recheck all selectors before implementation if other feature work lands first.

## Compatibility and Authority Contract

1. `WorldEngine` remains the sole objective mutation authority. This plan adds **no** world behavior: no new command, no new event, no new perception field, no new RNG stream, no new identifier namespace, no Alembic migration. Composition is expressed inside existing `Talk`/`Ask`/`Tell` relations.
2. The closed `AgentCommand` count stays **43**. The observer semantic-type count stays **73**. Replay stays `EVENT_SCHEMA_REPLAY_V22`, persistence codec stays `v20`, and `communication.v1` is unchanged. Only the runner schema advances to `runner-config-v46` when the new mode is enabled.
3. No new capability flag. `symbolic_language_mode` is a per-agent cognition treatment, default `DISABLED`, lockstep between `simulation.runner_models.SymbolicLanguageMode` and `agents.cognition.configuration.CognitionSymbolicLanguageMode`. It is not a `V2CapabilityFlags` or `V3CapabilityFlags` slot.
4. A deterministic symbolic mode requires the same agent's `semantic_naming_mode=DETERMINISTIC`. Symbolic mode on pre-v46, deterministic symbolic mode on v45, and symbolic mode without semantic naming reject with stable safe reason codes. `runner-config-v46` is emitted only when at least one agent's mode is `DETERMINISTIC`; absent symbolic mode keeps the prior highest-active schema and the default write remains `runner-config-v4`.
5. `runner-config-v46` is a mode-only increment. It adds no root sibling. When contact is active it carries the exact v45 family root keys; when contact is absent it carries the active v44-or-earlier family root keys. v46 never implies contact, regions, public goods, cultural memory, or any other channel.
6. A composed relation is **speaker testimony about symbol co-use**, not an objective world fact. The wire carries symbol tokens and a closed composition operator only; it never carries the speaker's referent hypothesis or a truth claim. The world does not validate `attributive` or `relational` as ontology.
7. Three layers stay separate:
   - **Objective entity:** opaque `EntityId` values and observed occurrence identity only.
   - **Subjective meaning:** an owner's `SymbolicComposition.referent_hypothesis` and confidence, stored only in that owner's ledger.
   - **Socially shared convention:** analysis-only prevalence/divergence rows; never a world object, never a shared dictionary, never fed back to agents.
8. Composition is bounded and non-recursive. Exactly two already-active label tokens per composition; exactly two closed operators (`attributive`, `relational`); at most two compositions per utterance; no nesting, no free-form text, no grammar induction, no invented lexemes. A composition cannot be minted unless both constituents are active in the owner's `TerminologyLedger`.
9. A listener never copies a speaker's composition, confidence, or referent hypothesis. It may add evidence only when its own terminology can resolve both constituents; otherwise it records `constituent_missing`/`constituent_inactive` and no composition. Memory may reinforce existing compositions only and never mints a new one.
10. Analysis is detached and read-only. New analysis modules import no persistence, runtime, world private modules, or subjective ledger types. `src/experiments/composition.py` performs joins from detached rows. Outputs use opaque IDs and token digests only; no symbol text, narration, prompts, or message bodies enter logs or metric documents.
11. Disabled/off behavior is byte-identical: no compositions, no new relations, no new IDs, no observation fields, no RNG consumption, no trajectory changes. Other owned V2/V3 flags remain independently optional.
12. Different populations are allowed to diverge. Contact may produce borrowing only through existing delivered communication and existing contact channels; no convergence, assimilation, or shared-convention success condition exists. `multi_hop_testimony_tracking` remains fail-closed.

## Design Decisions

### Per-agent mode and locked policy

- New `src/agents/cognition/symbolic_language.py` with `SYMBOLIC_LANGUAGE_POLICY_VERSION = "symbolic-language.v1"`.
- `SymbolicLanguageMode` values are `disabled` and `deterministic`; `CognitionSymbolicLanguageMode` mirrors it. The mode is per-agent, like semantic naming.
- Policy constants are locked in code and never serialized in runner JSON: active strength `0.40`, retire strength `0.20`, decay `0.05`, observed co-occurrence `0.12`, communicated composition `0.10`, remembered reinforcement `0.08`, self-use `0.06`, promotion count `3`, max compositions `8`, max evidence `24`, max compositions per message `2`, meaning-shift window `6`, utterance interval `4`.
- `runner-config-v46` carries only the mode. No weights, thresholds, or invented vocabulary are configurable.

### Owner-scoped composition contracts

- `SymbolicCompositionKind` is closed: `attributive` and `relational`. `attributive` means head symbol plus modifier symbol; `relational` means subject symbol plus relatum symbol. The distinction is a closed operator, not an inferred grammatical category.
- `SymbolicStatus` is closed: `candidate`, `active`, `retired`.
- `SymbolicEvidenceChannel` is closed: `observed`, `communicated`, `remembered`, `self_use`.
- `SymbolicParseOutcome` is closed: `parsed`, `partial`, `unresolved`, `ignored`.
- `SymbolicReferentHypothesis` holds a `NamingReferentKind` and a quantized confidence.
- `SymbolicComposition` holds `composition_id`, `owner_id`, `kind`, exactly two ordered `parts`, optional `referent_hypothesis`, `status`, `strength`, `evidence_count`, `usage_count`, `first_tick`, `last_tick`, `last_utterance_tick`, `sense_revision`, `notices`, and bounded `SymbolicEvidenceItem` rows.
- `composition_id` is an owner-scoped deterministic digest of `(owner_id, kind, parts)`; the same surface form used by two owners is intentionally two different composition IDs.
- `SymbolicEvidenceItem` holds `evidence_id`, `ordinal`, `channel`, `lineage_ref`, `tick`, optional `actor_id`, and optional `speaker_id`; it never holds another owner's hypothesis.
- `SymbolicLedger` holds `owner_id`, at most 8 compositions, at most 2 utterance plans, bounded notices, and the policy version.
- `SymbolicUtterancePlan` holds an ordered tuple of at most two compositions selected for one utterance.
- `SymbolicCueSummary` is an optional closed bag of opaque observed entity keys supplied by `CognitiveLoop`; it must not carry sibling ledgers, analysis rows, or free-form prose.
- Every constructor validates unknown enums, duplicate evidence, caps, owner mismatch, token shape, and id mismatch with safe reason codes. `symbolic_ledger.require_owner_symbolic_language(...)` mirrors the naming owner guard.

### Bounded composition grammar and wire shape

- A composition uses exactly two label tokens matching the existing `^[a-z][a-z0-9_]{0,31}$` shape. Both tokens must resolve to `ACTIVE` `LabelBinding` rows in the same owner's `TerminologyLedger`.
- Wire relations are ordinary `CommunicationRelation` atoms:
  - one `call` atom per constituent, preserved from the existing naming convention (`subject=token`, `object=referent_kind`);
  - one operator atom per composition (`subject=part_a`, `predicate=attributive|relational`, `object=part_b`).
- A message carries at most two operator atoms and at most four distinct constituent tokens. No relation carries a composition id, referent confidence, or semantic truth claim.
- A listener recognizes only the closed literals `attributive` and `relational`; any other predicate is `unsupported_predicate` and is ignored for composition learning. This is a cognition-level closed vocabulary, not a change to `communication.v1`.
- No nested compositions are allowed: composition parts must be label tokens, never composition ids. No recursive expansion, no generated morphology, no free-form sentence text.

### Learning, interpretation, and confidence

- `apply_symbolic_update(observation, identity, previous, terminology, memories=None, cues=None, policy=None)` runs after `apply_naming_update` in the same tick and reads the updated owner naming ledger.
- **Observed co-occurrence:** two active labels that repeatedly resolve to the same observed entity/logical occurrence become a composition candidate. The evidence channel is `observed`; the composition is not minted until the promotion count and strength thresholds are met.
- **Communicated composition:** when a delivered communication contains a recognized operator atom and both constituent tokens resolve to the listener's active bindings, the listener records `communicated` evidence. The listener's hypothesis is derived from its own constituent candidates when their top referent kinds agree; otherwise it stays `unresolved`. Speaker confidence is not copied.
- **Partial/unresolved messages:** if one or both constituents are not active in the listener's terminology, the listener records an outcome and a notice but creates no composition. This is the main mechanism that prevents lexical magic and population convergence without communication.
- **Memory reinforcement:** a live memory may reinforce an existing composition when its concepts/relations contain both parts. Memory never mints a composition and never adds a new part.
- **Promotion, merge, meaning shift, decay, retirement:** mirror the naming lifecycle with composition-specific caps. Compositions merge only when kind and both parts match exactly; no similarity-based merge of different surface forms. Decay uses logical ticks only.
- **Usage:** selecting a composition for an emitted `Talk` increments `usage_count` and sets `last_utterance_tick`, subject to the utterance interval. Non-selected proposals do not add usage. Listener-side interpretation outcomes are recorded separately and never count as speaker usage.
- **Confidence separation:** the ledger stores the owner's hypothesis confidence; `StructuredUtterance.declared.sender_confidence` remains the existing speaker-declared channel value. The two are never synchronized automatically.

### Outbound selection and integration

- `symbolic_communicate_utterance` runs after `naming_communicate_utterance` and only for an existing `Talk` command. If no active, speakable composition exists, it returns the naming command unchanged.
- Selection is deterministic: active status, strength threshold, constituent availability, utterance interval, stable tie-break by `(strength, composition_id)`. Relevance uses the owner's current observation/cues only.
- A selected composition rebuilds the `StructuredUtterance` with the constituent `call` atoms and the operator atom, preserving recipient and declared transmission fields. At most two compositions are emitted. The function never chooses a new recipient or creates a new command kind.
- `loop.py` gains `_prepare_symbolic_language` and a closed cue builder; `deliberation.py` receives the ledger and applies the stamping hook. Naming remains the first composition source; symbolic composition may replace the naming-only utterance only when a composition is selected.
- `Ask`/`Tell` remain unchanged unless the implementation reuses the same utterance construction path; in either case no new command semantics are introduced.

### Runtime carrying and blank-slate behavior

- `AgentRuntimeState` gains `_symbolic_language`; `AgentRuntimeCheckpoint` gains `symbolic_language`; the runtime commits after the cognitive loop and restores from checkpoints alongside `semantic_naming`.
- `perception.py` passes `symbolic_language` into the cognition snapshot. It stays researcher-only and is never added to objective observer frames.
- `new_agent_initialization.py` adds `symbolic_language` to the blank-slate exclusion set, exactly like `semantic_naming`. A new agent starts with an empty ledger and no inherited vocabulary.
- Owner validation rejects foreign ledgers with a stable `owner_mismatch` error; disabled mode clears the carried ledger.

### Detached analysis and social distribution

- New `src/analysis/symbolic_language_metrics.py` owns three families:
  - `symbolic_composition@1` — owner-level inventory: active/candidate/retired counts, operator mix, constituent-digest diversity, strength bands, usage counts, interpretation counts, unresolved-composition counts, coverage.
  - `symbolic_social_distribution@1` — candidate-community prevalence of composition surface digests, adoption/reinforcement counts, cross-population borrowing through communicated evidence, pairwise divergence, coverage gaps, and singleton handling. It reuses `society_emergence` candidate-community rows when present and reports `absent` when they are unavailable.
  - `symbolic_message_flow@1` — composed-message counts, operator mix, composition arity, parse outcomes (`parsed`/`partial`/`unresolved`/`ignored`), speaker-listener pair counts, unresolved constituent counts, and declared-confidence bands. It reports structural parse results, never semantic correctness.
- Detached row contracts live in the analysis module and are built in `src/experiments/composition.py`:
  - `SymbolicCompositionRow(owner_id, composition_id, kind, part_digests, referent_kind, status, strength_band, usage_count, tick_range)`
  - `SymbolicMessageRow(message_id, speaker_id, listener_id, tick, kind, part_digests, parse_outcome, declared_confidence_band)`
  - `SymbolicInterpretationRow(owner_id, message_id, outcome, composition_id, tick)`
- Token digests are computed with the existing SHA-256 conventions; metric documents never expose raw symbol text. A surface-form digest may be compared across owners, but the owner-scoped `composition_id` must not be used as a shared identity.
- Social distribution is descriptive. A high-prevalence pattern is reported as a distribution band, not written back as a "convention" object. No agent receives prevalence, community labels, or borrowing results.

### Experiment BB (off the V1 regression gate)

- New `src/experiments/symbolic_language_scenario.py` plus catalog builder `experiment_bb_symbolic_language`; experiment id `compositional_symbols@1`; register in `OFF_GATE_MATRIX_EXPERIMENT_IDS` and runtime dispatch, following BA.
- Arms: `bb-off` (symbolic disabled), `bb-single` (one population, naming + symbolic deterministic), `bb-isolated` (two region-separated populations, naming + symbolic, no contact), `bb-contact` (two region-separated populations with owned contact/trade/teaching channels), and a non-run `bb-unsupported` config fixture asserting symbolic mode without naming rejects.
- The arbiter asserts only structural facts: off arm emits no compositions or composed messages; single arm produces active compositions and at least one composed `Talk`; isolated populations have different surface-digest sets and no cross-population composed messages; contact borrowing appears only for delivered communications; listener interpretations are owner-scoped; no global lexicon or shared-convention authority exists; no unexplained cross-population transmission exists without a journey/contact channel. It never asserts that convergence, agreement, or "better language" succeeded.

### Presentation and documentation

- Add a researcher-only symbolic view, not an objective event: `GET /{run_id}/observer/agents/{agent_id}/symbolic-language` returning `ObserverSymbolicOverlayOut` from the owner checkpoint. Objective frames and Godot `KNOWN_TYPES` remain unchanged.
- Optionally add a `SymbolicLanguagePanel.svelte` under the existing research-inference chrome using the `analytical_inference` class. It reads only the generic researcher endpoint and shows digests/bands/counts, never prompts or message bodies.
- Documentation: `docs/social-communication.md` (composition semantics and limits), `docs/configuration.md` (v46 and per-agent mode), `docs/architecture.md` (schema/boundary/counts), `docs/experiments.md` (Experiment BB and matrix selection), `docs/analysis-metrics.md` (three new families, 103 → 106), `docs/persistence.md` and `docs/simulation-runner.md` (v46; replay/codec unchanged), `docs/research-api.md` / `docs/research-ui.md` (researcher endpoint/panel), `docs/development.md` (verification block), and README index if a new page is added.

## Commit Plan

Commit messages are suggestions for implementation; this planning command creates no commits.

- **Commit 1** (tasks 1–2): `feat(v3): add symbolic composition contracts and runner-config-v46`
- **Commit 2** (tasks 3–6): `feat(v3): learn, compose, and carry owner-scoped symbolic messages`
- **Commit 3** (tasks 7–11): `feat(v3): add detached symbolic composition and distribution metrics`
- **Commit 4** (tasks 12–13): `feat(v3): add Experiment BB and researcher symbolic view`
- **Commit 5** (tasks 14–15): `docs(v3): document symbolic language contracts and metrics`
- **Commit 6** (task 16): `test(v3): reconcile symbolic-language gates and compatibility counts`

## Tasks

### Phase 1 — Contracts and configuration

- [x] **Task 1: Define the owner-scoped symbolic composition contract with exact validation.**
  - Files: create `src/agents/cognition/symbolic_language.py`; update `src/agents/cognition/__init__.py`; create `tests/unit/test_symbolic_language.py`.
  - Deliver `SYMBOLIC_LANGUAGE_POLICY_VERSION`, `SymbolicCompositionKind`, `SymbolicStatus`, `SymbolicEvidenceChannel`, `SymbolicParseOutcome`, `SymbolicReferentHypothesis`, `SymbolicEvidenceItem`, `SymbolicComposition`, `SymbolicLedger`, `SymbolicUtterancePlan`, `SymbolicCueSummary`, `SymbolicLanguagePolicy`, `default_symbolic_language_policy`, `empty_symbolic_ledger`, `require_owner_symbolic_language`, and deterministic composition/evidence id helpers.
  - Enforce exactly two label-shaped parts, owner-scoped id derivation, caps (8 compositions, 24 evidence items, 2 utterance-plan compositions), closed enums, duplicate/self-reference rejection, quantized confidence, and policy-version locking. The contract must reject `TerminologyLedger` embedded as a part and must reject world authority or sibling ledger objects as cue content.
  - Acceptance: frozen values round-trip; caller mutation cannot alter them; identical inputs produce identical ids across processes; unknown enums/operators/caps reject with stable reason codes; importing the module does not import analysis, persistence, or world private modules.
  - Logging: DEBUG at validation boundaries with owner id, counts, enums, and safe reason codes only; never symbol text or entity labels. Pure constructors need no side-effect logs.
  - Dependencies: none.

- [x] **Task 2: Gate and serialize the per-agent symbolic mode as `runner-config-v46`.**
  - Files: `src/agents/cognition/configuration.py`, `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/runner.py`, `src/simulation/compatibility.py`, `src/simulation/matrix_schema.py`, `src/simulation/__init__.py`; create `tests/unit/test_runner_config_v46.py`; update `tests/unit/test_compatibility_matrix.py`, `tests/unit/test_v3_flag_defaults.py`, `tests/unit/test_runner_config_v45.py`.
  - Add `CognitionSymbolicLanguageMode` and `SymbolicLanguageMode` (`disabled`/`deterministic`) and `AgentCognitionSpec.symbolic_language_mode`. Require `semantic_naming_mode=DETERMINISTIC` when symbolic mode is deterministic (`symbolic_language_requires_semantic_naming`); reject deterministic symbolic mode on any schema below v46 (`symbolic_language_requires_v46`); require at least one deterministic mode for v46 (`v46_requires_symbolic_language`). Accept `disabled` only with the matching schema rules.
  - **Schema sweep (required):** add v46 to `SUPPORTED_RUNNER_SCHEMA_VERSIONS`, every family/mode allowlist that currently includes v45, `regions_migration`/contact/public-goods/collective-project/historical-memory schema sets, agent-cognition encode/decode allowlists, `matrix_schema` highest-wins selection before v45, `compatibility` matrix/debug maps, and facade exports. Map v46 to the active v44/v45 family-root key builder; do **not** add a new root sibling. `runner-config-v46` must compose legally with contact on or off.
  - Acceptance: v1–v45 keysets and selectors unchanged; contact-off v46 carries no contact key; contact-on v46 carries the exact v45 root; disabled mode keeps the prior schema/default write `runner-config-v4`; all owned/unowned flag gates remain fail-closed; matrix encoding round-trips with every legal prior channel.
  - Logging: INFO at activation with schema/mode; DEBUG gate decisions; WARN invalid combinations with stable codes only. No config dumps or per-agent token content.
  - Dependencies: 1.

### Phase 2 — Cognition and runtime

- [x] **Task 3: Implement observed and remembered composition learning.**
  - Files: `src/agents/cognition/symbolic_language.py`; create `tests/unit/test_symbolic_language_learning.py`.
  - Implement `apply_symbolic_update(...)` with the observation/co-occurrence path and memory-reinforcement path. Resolve parts against the supplied owner `TerminologyLedger`; only `ACTIVE` bindings are eligible. Repeated co-occurrence of the same two label candidates on the same observed entity creates `observed` evidence; live memories may reinforce existing compositions only. Add promotion, merge-exact, meaning-shift, decay, retirement, and freeze phases.
  - Do not mint a composition from one observation, from a single shared location token, or from memory alone. Reject previous ledgers with the wrong owner. Keep the function import-closed from analysis and world authority.
  - Acceptance: known-answer sequences produce deterministic candidate→active transitions; one-sided or inactive constituents produce notices and no composition; identical seeds/observations produce identical ids/strength bands; memory cannot invent a part; caps stop growth without exceptions.
  - Logging: DEBUG for each update phase with counts and reason codes; INFO once per updated ledger with owner id, composition count, and status counts. Never log symbol text, entity labels, or memory content.
  - Dependencies: 1, 2.

- [x] **Task 4: Implement listener-side communicated composition parsing and interpretation.**
  - Files: `src/agents/cognition/symbolic_language.py`; create `tests/unit/test_symbolic_language_transmission.py`.
  - Parse only `attributive`/`relational` operator atoms from `ObservedCommunication` addressed to the owner. Require both parts to resolve to active owner bindings; otherwise record `partial`/`unresolved` and a notice with no new composition. Record `communicated` evidence and a listener-derived referent hypothesis only when the owner's constituent candidates agree on a kind; never copy the speaker's hypothesis, strength, or confidence.
  - Deduplicate by `(composition surface, communication lineage, channel)`; keep evidence bounded. Ignore non-owner communications and unsupported predicates safely. Preserve existing one-hop testimony semantics; do not create multi-hop component tracking.
  - Acceptance: a listener with both constituents learns a candidate; a listener missing one constituent learns nothing; two listeners with different constituent meanings form different hypotheses; repeated delivered messages reinforce only the recipient; malformed/oversized relations drop with safe codes.
  - Logging: DEBUG with owner id, speaker id, outcome, and counts only; no tokens, utterance text, or confidence values beyond bands.
  - Dependencies: 3.

- [x] **Task 5: Add deterministic outbound composition selection and utterance stamping.**
  - Files: `src/agents/cognition/symbolic_language.py`, `src/agents/cognition/deliberation.py`, `src/agents/cognition/loop.py`; create `tests/unit/test_symbolic_language_runtime.py`; update `tests/unit/test_semantic_naming_world.py`.
  - Implement `symbolic_communicate_utterance` and the loop/deliberation hooks. Run after naming stamping, only for an existing `Talk`. If no speakable composition exists, return the command unchanged. If one exists, rebuild the utterance with the constituent `call` atoms and one operator atom per composition, capped at two compositions, preserving recipient and declared transmission. Add `symbolic_language` to the deliberation context and commit usage only for the selected command.
  - Keep naming behavior intact when symbolic mode is disabled or no composition qualifies. `Ask`/`Tell` must not gain new semantics.
  - Acceptance: disabled mode returns the exact same command object; no active composition leaves naming output unchanged; selected composition produces a bounded, deterministic relation set; listener parsing in Task 4 can reconstruct the composition; rejected proposals do not increment usage.
  - Logging: DEBUG selection with candidate count, operator, usage band, and outcome; INFO once per emitted composed message with speaker/listener ids and composition counts. Never log tokens or utterance text.
  - Dependencies: 3, 4.

- [x] **Task 6: Carry the symbolic ledger through checkpoints, perception, and blank-slate bootstrap.**
  - Files: `src/simulation/run_control.py`, `src/simulation/agent_runtime.py`, `src/simulation/perception.py`, `src/simulation/new_agent_initialization.py`; create `tests/unit/test_symbolic_language_checkpoint.py`; update `tests/unit/test_semantic_naming_runtime.py`.
  - Add `symbolic_language` to `AgentRuntimeState`, `AgentRuntimeCheckpoint`, snapshot construction, commit/restore, and owner validation. Clear it when mode is disabled. Add `symbolic_language`/`symbolic_ledger` to blank-slate exclusion sets so new agents never inherit compositions.
  - Acceptance: enabled ledger round-trips exactly; foreign-owner ledgers reject; disabled runs carry `None`; checkpoint restore produces identical subsequent cognition; new-agent initialization contains no symbolic fields; objective observer frames still reject the field.
  - Logging: DEBUG on carry/restore with owner id, composition count, tick; INFO on mode activation/deactivation; no tokens.
  - Dependencies: 3.

### Phase 3 — Detached analysis

- [x] **Task 7: Define detached symbolic rows and harvest them in composition.**
  - Files: create `src/analysis/symbolic_language_metrics.py` (row DTOs first); update `src/experiments/composition.py`, `src/experiments/collectors.py`, `src/experiments/metric_collection.py`, `src/analysis/__init__.py`; create `tests/unit/test_symbolic_language_rows.py`.
  - Deliver `SymbolicCompositionRow`, `SymbolicMessageRow`, and `SymbolicInterpretationRow` with frozen validation, digest-only parts, closed outcomes/kinds, tick ranges, and no raw tokens. Harvest from detached checkpoints/ledgers and detached `Talked`/`Asked`/`Told` evidence. Resolve speaker/listener IDs and candidate-community membership only through existing detached rows.
  - Acceptance: rows round-trip; missing checkpoints or absent communications yield coverage gaps rather than fabricated zeros; no analysis module imports ledger types; cross-owner surface digests are stable; raw tokens never appear in documents or logs.
  - Logging: DEBUG with row counts and coverage bands; INFO once per harvest; no ids beyond opaque values and no content.
  - Dependencies: 1, 6.

- [x] **Task 8: Implement `symbolic_composition@1`.**
  - Files: `src/analysis/symbolic_language_metrics.py`, `src/analysis/specifications.py`; create `tests/unit/test_symbolic_composition_metrics.py`.
  - Compute owner-level inventory, status/operator mix, strength bands, usage counts, interpretation counts, unresolved-composition counts, and coverage. Availability is `absent` when no symbolic rows exist; never infer zeros for missing owners.
  - Acceptance: known-answer rows produce pinned counts; candidate/active/retired separation is exact; usage and interpretation totals are not double-counted; deterministic fingerprints for identical inputs; empty input yields `absent`.
  - Logging: INFO at assembly with family id and availability; DEBUG with aggregate counts only.
  - Dependencies: 7.

- [x] **Task 9: Implement `symbolic_social_distribution@1`.**
  - Files: `src/analysis/symbolic_language_metrics.py`, `src/analysis/specifications.py`; create `tests/unit/test_symbolic_distribution_metrics.py`.
  - Join detached composition rows to candidate-community rows when available. Report per-community prevalence of surface digests, adoption/reinforcement from communicated evidence, cross-population borrowing (speaker community differs from owner community), pairwise divergence using the existing numerical/JS helpers, singleton/unassigned coverage, and `absent`/`partial` availability. Reuse `society_emergence` rows; do not invent communities.
  - Acceptance: two isolated populations with disjoint surface sets show maximum divergence; no-contact runs show zero borrowed compositions; contact runs count borrowing only for delivered communications; missing communities yield `absent`, not zero; aggregate outputs never identify an owner's meaning as shared truth.
  - Logging: INFO with family id, community count, and availability; DEBUG with aggregate pair/coverage counts only.
  - Dependencies: 7.

- [x] **Task 10: Implement `symbolic_message_flow@1`.**
  - Files: `src/analysis/symbolic_language_metrics.py`, `src/analysis/specifications.py`; create `tests/unit/test_symbolic_message_flow_metrics.py`.
  - Compute composed-message counts, operator mix, arity, parse outcomes, speaker-listener pair counts, unresolved constituent counts, and declared-confidence bands. Treat parse outcomes as structural, not semantic correctness.
  - Acceptance: a delivered message with two compositions counts two operator atoms and at most four constituents; missing listeners or unresolved recipients are coverage gaps; unsupported predicates are `ignored`; identical message rows produce identical documents.
  - Logging: INFO at assembly with availability; DEBUG with aggregate outcome counts only; no message ids in logs.
  - Dependencies: 7.

- [x] **Task 11: Register the three families and wire metric assembly.**
  - Files: `src/analysis/specifications.py` (`METRIC_FAMILY_COUNT` 103 → 106), `src/analysis/metric_service.py`, `src/analysis/__init__.py`, `src/analysis/serialization.py`; update `tests/unit/test_metric_specifications.py`, `tests/unit/test_metric_service.py`, and every unit test that hardcodes `METRIC_FAMILY_COUNT == 103` (find with `rg -l "METRIC_FAMILY_COUNT == 103" tests/unit`).
  - Add opt-in assembly branches behind the existing `_safe` wrapper. Flags-off runs must emit `absent` availability or omit the families according to the current catalog convention without errors. Cross-version comparison remains unchanged.
  - Acceptance: catalog validation passes at 106; all three specs are discoverable by family id; flags-off baseline remains green; metric documents expose only digests/bands/counts; no unsupported family is accepted by serialization.
  - Logging: INFO at assembly with each family id and availability; WARN on absent/degraded inputs with safe codes.
  - Dependencies: 8, 9, 10.

### Phase 4 — Experiment, presentation, and documentation

- [x] **Task 12: Add Experiment BB and dispatch.**
  - Files: create `src/experiments/symbolic_language_scenario.py`; update `src/experiments/catalog.py`, `src/experiments/__init__.py`, `src/experiments/coordinator.py`, `src/experiments/matrix_runner.py`; create `tests/unit/test_experiment_bb.py`.
  - Implement `compositional_symbols@1` with `bb-off`, `bb-single`, `bb-isolated`, `bb-contact`, and the `bb-unsupported` config fixture. Register it off the V1 gate following BA. Keep the scenario deterministic and matrix-compatible.
  - Arbiter: off arm has no symbolic rows; single arm has active compositions and a composed `Talk`; isolated arms have population-specific surface digests and no cross-population composed messages; contact arms show borrowing only via delivered communication; no arm creates a global lexicon or shared-convention object; unsupported config fails closed.
  - Acceptance: all arms run under the same seed/scenario identity where applicable; deterministic results across runs; catalog/count assertions updated; no experiment claims semantic correctness or convergence success.
  - Logging: INFO at scenario build/arbitration with arm id and aggregate counts; DEBUG with safe structural details only.
  - Dependencies: 2, 5, 11.

- [x] **Task 13: Add researcher-only symbolic presentation.**
  - Files: `src/api/routes/observer.py`, `src/api/observer_schemas.py`, `src/observer/labels.py` (new overlay), `src/observer/__init__.py`; create `tests/unit/test_symbolic_language_observer.py`; optionally update `clients/research-ui/` with a new panel.
  - Add `GET /{run_id}/observer/agents/{agent_id}/symbolic-language` reading `manager.owner_runtime_checkpoint(...).symbolic_language`, with tick gating and owner checks matching the labels endpoint. Return compositions as digest/bands/counts, never raw tokens or referent entity labels.
  - Acceptance: objective frames still reject symbolic fields; the endpoint is read-only and checkpoint-backed; disabled/empty ledgers return an empty overlay; no new observer semantic type or Godot router entry; existing label endpoint behavior unchanged.
  - Logging: INFO per request with run/agent ids and counts; DEBUG with outcome only; never symbol text.
  - Dependencies: 6.

- [x] **Task 14: Update core documentation for the contracts and configuration.**
  - Files: `docs/social-communication.md`, `docs/configuration.md`, `docs/architecture.md`, `docs/persistence.md`, `docs/simulation-runner.md`.
  - Document the binary grammar, owner-scoped meaning, listener hypothesis formation, no-shared-lexicon rule, v46 per-agent mode and prerequisites, the unchanged command/event/replay/codec pair, and the 43/73/106 counts. Update the version taxonomy, write-pair priority, downstream V3 checklist, and v45→v46 matrix wording.
  - Acceptance: docs match code selectors; no stale claim that composition changes `communication.v1`; all internal links resolve; no unsupported capability or convergence claim.
  - Logging: not applicable to docs, but examples must use metadata-only output and never print tokens or message bodies.
  - Dependencies: 11, 12.

- [x] **Task 15: Update experiments, metrics, presentation, and development documentation.**
  - Files: `docs/experiments.md`, `docs/analysis-metrics.md`, `docs/research-api.md`, `docs/research-ui.md`, `docs/development.md`, `README.md` (index if needed).
  - Add Experiment BB, the three families, researcher endpoint/panel, verification block, and the 103 → 106 family count. State that composition distribution is descriptive and that different vocabularies are a valid outcome.
  - Acceptance: links/anchors resolve; docs identify the exact verification commands; README index remains complete.
  - Logging: not applicable to docs.
  - Dependencies: 11, 12, 13.

- [x] **Task 16: Reconcile architecture, compatibility, and full verification gates.**
  - Files: tests and any narrowly required wiring discovered by verification; do not weaken gates. Update `tests/architecture/` isolation/import tests and all count pins.
  - Verify: focused symbolic tests; `uv run --frozen --python 3.12.14 pytest`; Ruff; mypy; import-linter; architecture suite; the required six-file V1/V2 compatibility gate; the V3 flags-off scientific-invariant gate; and the new BB/runner-v46 focused suites. Confirm Alembic head stays `0017`, replay/codec pair stays `v22`/`v20`, command count stays 43, and observer semantic count stays 73.
  - Acceptance: no new gate exclusions or suppressed errors; disabled runs remain byte-identical; v46 round-trips in runner config and matrix schema; experiment BB and all three metric families are registered and tested.
  - Logging: record verification outcomes and any safe failure codes in the plan log; never paste tokens, message bodies, or prompts.
  - Dependencies: 1–15.

## Verification Notes

- Focused suites to add or run during implementation:
  - `tests/unit/test_symbolic_language.py`
  - `tests/unit/test_symbolic_language_learning.py`
  - `tests/unit/test_symbolic_language_transmission.py`
  - `tests/unit/test_symbolic_language_runtime.py`
  - `tests/unit/test_symbolic_language_checkpoint.py`
  - `tests/unit/test_symbolic_language_rows.py`
  - `tests/unit/test_symbolic_composition_metrics.py`
  - `tests/unit/test_symbolic_distribution_metrics.py`
  - `tests/unit/test_symbolic_message_flow_metrics.py`
  - `tests/unit/test_runner_config_v46.py`
  - `tests/unit/test_symbolic_language_observer.py`
  - `tests/unit/test_experiment_bb.py`
- Required repository gates: default pytest, Ruff, mypy, import-linter, architecture isolation, V1/V2 compatibility, and V3 flags-off invariants. No Godot suite is required because no observer semantic type, router entry, or protocol shape changes.
- Manual reviewer checks: confirm composition ids are owner-scoped; confirm a listener with a missing constituent cannot acquire a composition; confirm no analysis document or log contains raw tokens; confirm contact borrowing requires delivered communication; confirm disabled arms are byte-identical.
