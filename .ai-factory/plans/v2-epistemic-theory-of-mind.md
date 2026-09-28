# Implementation Plan: Explicit Epistemic Theory of Mind

Branch: main
Created: 2026-09-28

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M6 — Remaining V2 Capability Flags"
Rationale: First incomplete milestone; this plan extends the owned `advanced_social_inference` mind with a bounded epistemic ledger and leaves `multi_hop_testimony_tracking` unowned.

## Compatibility contract

This plan adds an owner-scoped epistemic ledger beside the existing first-order `TheoryOfMind`. It must satisfy the Downstream V2 plan contract in `docs/architecture.md`.

1. V1 invariants intact. `WorldEngine` remains the only mutation authority. An update reads the owner's `Observation`, the owner's own `SemanticBelief` heads, reconstructed memories already retrieved for that owner, and epistemic rows already stored on that owner's mind model. It never receives `WorldState`, `PhysicalRules`, `AgentBody`, `WorldEvent`, an event repository, replay, analysis truth, or another agent's runtime, goals, drives, beliefs, emotion, relationships, memories, or mind model.
2. No new capability flag. `advanced_social_inference` stays the only switch. Default remains off. Off is still a passthrough: `CognitiveLoop._prepare_theory_of_mind` returns `None`, the epistemic updater is not called, communication judgments are not computed, and the trace stays `unavailable` / `tom_not_implemented`. `multi_hop_testimony_tracking` stays unimplemented and still fails closed with `capability_unimplemented`.
3. V1 regression gate stays green under flags-off and tracing-off. Catalog A–E and the reference scenario keep their current `exact_trajectory_hash` values. Experiment L and the new Experiment M stay off `tests/unit/test_v1_regression_gate.py`.
4. No runner schema bump. Do not add policy knobs to runner JSON. Do not add `runner-config-v9`. `RUNNER_SCHEMA_VERSION` stays `runner-config-v4`. Depth and thresholds live on `EpistemicPolicy`.
5. No scripted emergence. Example sentences in this plan are meanings of structured rows. There is no friend, enemy, leader, trader, or culture label, and no new `AgentCommand`, `ActionDirection`, or `CommunicationSourceBasis`.
6. No LLM path. Epistemic update and disclosure never call `LLMProvider`. Do not add a prompt package or an import-linter ignore.
7. Experiments stay reproducible. Experiment M arms share seed, scenario, and stochastic identity. Analysis, if present on an audit snapshot, runs after the run and is not fed back into cognition.
8. Optional cognition tracing stays outside the objective fold. Do not insert a `ComponentKind` or an ordinal in `_STAGE_ORDER`. Do not bump `COGNITION_TRACE_SUMMARY_SCHEMA`, add trace enum members, or add an Alembic revision. Do not put epistemic atoms on the trace summary. Tracing on versus off must not change `exact_trajectory_hash`.
9. First-order hypotheses stay first-order. `MindHypothesis` still has no child model. `_reject_nested` still rejects `believes`, `thinks`, `wants`, `feels`, `knows`, and `intends` on hypothesis atoms with `nested_mind_rejected`. This plan does not reopen that path.

## Goal

When `V2CapabilityFlags.advanced_social_inference` is enabled, each agent keeps a private flat epistemic ledger in addition to first-order mind hypotheses. The sentences below are the meanings of those rows. They are not stored prose.

| Meaning | Nesting | Modeled agents | Attitude | Proposition |
| --- | --- | --- | --- | --- |
| Alice knows X | 1 | none (the owner) | `KNOWS` | X |
| Alice believes X | 1 | none | `BELIEVES` | X |
| Alice is uncertain about X | 1 | none | `UNCERTAIN` | X |
| Alice believes Bob knows X | 2 | Bob | `KNOWS` | X |
| Alice believes Bob does not know X | 2 | Bob | `DOES_NOT_KNOW` | X |
| Alice believes Bob believes X | 2 | Bob | `BELIEVES` | X |

The store owner is implicit on every row. "Alice believes Bob knows X" is one row in Alice's ledger. It is not a `MindHypothesis` and not a pointer to Bob's ledger.

Nesting depth is configurable on `EpistemicPolicy.max_depth` and hard-capped. The deterministic updater emits only levels 1 and 2. Level 3 may be constructed in tests when `max_depth` is 3. Nothing emits level 4 or a recursive child list.

Communication planning uses a closed judgment over a recipient and a proposition: new to that agent, already known, secret, uncertain, or contradictory.

## Design Decisions (locked)

- **Separate ledger, same store.** Add `attributions: tuple[EpistemicAttribution, ...] = ()` on `TheoryOfMind`. Empty is the default, so existing constructors keep working. Attributions are not `SemanticBelief` records, not `MindHypothesis` rows, and not relationship dimensions. Do not emit `BeliefRevisionRequest` from an epistemic update. First-order `KNOWLEDGE` and `BELIEF` hypotheses stay as they are. `src/agents/cognition/epistemic.py` imports `TheoryOfMind`. `theory_of_mind.py` does not import `epistemic` at module level. `TheoryOfMind.__post_init__` validates each attribution with a function-local import of `EpistemicAttribution`.
- **No recursive structure.** `EpistemicAttribution` has no field whose type is `EpistemicAttribution`. Nesting is an integer plus a tuple of agent ids. `modeled_agents` length is `nesting_level - 1`. Level 1 uses an empty tuple, meaning the owner's own attitude. Reject `nesting_level < 1`, a chain whose length does not match, and `nesting_level > _MAX_EPISTEMIC_DEPTH` (`3`) with `epistemic_depth_rejected`.
- **Configurable cap.** `EpistemicPolicy.version` is `epistemic-model-v1`. `max_depth` defaults to `2` and must satisfy `0 <= max_depth <= 3`. `max_depth == 0` adds nothing and drops nothing: `update_epistemic_state` returns the model with its current `attributions` unchanged, and disclosure returns `None`. A row with `nesting_level > max_depth` is dropped with `epistemic_depth_exceeded` when it comes from a cue. The constructor itself only enforces the hard cap of 3, so a detached fixture can still build a legal level-3 row. `update_epistemic_state` refuses to keep a row above the policy depth.
- **Updater ceiling is 2.** Witness and testimony cues produce levels 1 and 2 only. They never invent a third agent. Level 3 exists so tests can prove the cap: a chain of length 2 (Bob, Carol) is legal only when `max_depth >= 3`, and a chain of length 3 always fails the hard cap. There is no function that walks a row to build a deeper row.
- **Self stays out of the chain.** Every id in `modeled_agents` must be an agent id already visible to the owner and must not equal the owner. Drop or reject with `self_subject`. Level 1 is the only place the owner is the attitude holder, and that is represented by an empty chain, not by putting the owner in `modeled_agents`. This blocks "Alice believes Bob believes Alice believes X".
- **Closed attitudes.** `EpistemicAttitude`: `KNOWS`, `BELIEVES`, `UNCERTAIN`, `DOES_NOT_KNOW`. Level 1 allows only `KNOWS`, `BELIEVES`, and `UNCERTAIN`. `DOES_NOT_KNOW` at level 1 is `epistemic_attitude_rejected`. Levels 2 and 3 allow all four.
- **Proposition reference.** `proposition_ref` is a stable id, not prose. Two forms, both produced by `epistemic_proposition_ref`:
  - `belief:<BeliefId.value>` when the owner's `SemanticBelief` is the source.
  - `fact:<occurrence kind>:<location id or none>` when the source is a witnessed occurrence. Kind and location are copied from the owner's observation. No `|` or `=` characters; reuse `require_stable_id` rules.
  - A row stores exactly one `proposition_ref`. It may also store `belief_id: str | None` when the form is `belief:`.
- **Confidence.** Occurrence and testimony rows reuse `confidence_from_masses` and `_EFFECT_QUANTUM = 1e-6` with `prior = 1`. Observed behavior weight `4`. Testimony weight `2`. Do not add a second quantum. A level-1 row from an `ACTIVE` `SemanticBelief` copies `BeliefConfidenceState.confidence` directly and stores `contradiction_mass` on the row. `support_mass` and `contradiction_mass` are already unit-interval values. Do not pass them through `prior = 1` (support `1` and counter `0` would become confidence `0.5` and could never reach `knows_threshold`). Attitude from that copied confidence: at or above `knows_threshold` (`0.8`) with `contradiction_mass == 0` → `KNOWS`; else at or above `believes_threshold` (`0.55`) → `BELIEVES`; else `UNCERTAIN`. When `contradiction_mass` is at or above `contradiction_threshold` (`0.5`), still write the row with attitude `UNCERTAIN`. Disclosure of that row is `CONTRADICTORY`. Confidence is not an engine probability and not a read of the other agent's confidence.
- **Source and provenance.** `EpistemicSource`: `SEMANTIC_BELIEF`, `OBSERVED_BEHAVIOR`, `COMMUNICATION`, `DERIVED`. Each row stores `source`, `provenance_ids` (cap `max_history` 32, oldest dropped), and `nesting_level`. Provenance ids are opaque strings the owner already holds: belief ids, observation provenance ids, or parent hypothesis ids. No utterance text.
- **Witness set.** A level-1 belief row stores `witness_ids`, cap 16. On each refresh, union the ids already on that row with the visible body ids from the current observation when this update ties the belief to a public occurrence the owner is recording. Drop overflow by sorted id. Those ids persist across ticks. They are who appeared co-present to the owner, not a read of anyone's perception. A `fact:` occurrence row may store the visible body ids from the tick it was created. A `fact:` row does not select a `Tell`.
- **Level 1 from the owner's beliefs.** Use `RetrievedMemoryContext.semantic_beliefs`. When that tuple is empty, use `SubjectiveSnapshot.semantic_beliefs`. Only `BeliefActivationState.ACTIVE` heads produce rows. `CANDIDATE` and `RETIRED` drop with `belief_inactive`. One row per belief id, `proposition_ref` `belief:<BeliefId.value>`, source `SEMANTIC_BELIEF`. Copy `BeliefConfidenceState.confidence`. Write the row even when `contradiction_mass` is at or above `0.5`; the stored attitude is then `UNCERTAIN`, and disclosure reads the mass. Missing beliefs create nothing. Refreshing a row unions `witness_ids` with any new witnesses from this observation. An empty `witness_ids` tuple means the belief was never tied to a public occurrence recorded on this ledger.
- **Level 2 `KNOWS` from co-presence.** For a level-1 `OBSERVED_BEHAVIOR` proposition, each other agent id in that row's `witness_ids` gets a level-2 `KNOWS` row, source `DERIVED`, provenance the level-1 row id. This is the hypothesis that the co-present agent noticed the same public event. It does not read that agent's observation.
- **Level 2 `DOES_NOT_KNOW`.** Write it only when all of the following hold: a level-1 `KNOWS` or `BELIEVES` row exists for proposition P; its source is `OBSERVED_BEHAVIOR` or `SEMANTIC_BELIEF`; subject B is on `visible_bodies` in the current observation; B is not the owner; B is not in that proposition's `witness_ids`; no level-2 `KNOWS` or `BELIEVES` row for (B, P) is already at or above `action_threshold`. Silence of an agent who is not currently visible creates nothing. One row per (B, P).
- **Level 2 from a single communication relation.** Read `Observation.communications` directly. `_relation_atoms` still returns `nested_mind_rejected` for these predicates, so they never arrive as `MindCue`s. Accept a relation only when the utterance has exactly one relation, `hop_count` is 1, the subject token equals a visible agent id that is not the owner, and the object is one allowlisted concept (`food`, `water`, `rest`, `danger`) or one `fact:` proposition key already on this model. Closed predicates: `knows` → `KNOWS`, `believes` → `BELIEVES`, `uncertain` → `UNCERTAIN`, `does_not_know` → `DOES_NOT_KNOW`. Anything else, including `wants`, `feels`, `intends`, `thinks`, and a relation whose object is itself one of those predicates, stays on the hypothesis path and still drops with `nested_mind_rejected`. `hop_count > 1` still drops with `multi_hop_deferred` and does not implement `multi_hop_testimony_tracking`. Testimony does not create a level-3 row.
- **Identity.** Attribution id is `ep-` plus the sha256 prefix of owner, nesting level, canonical modeled-agent chain, attitude, and `proposition_ref`, following `mind_hypothesis_id_for`. No RNG, wall clock, or Python `hash()`.
- **Caps.** `max_attributions` 64. When full, drop the lowest confidence, then the oldest last-update tick, then the greater id. Same ordering idea as hypothesis eviction.
- **Disclosure.** `epistemic_disclosure(model, recipient_id, proposition_ref, policy) -> EpistemicDisclosure | None`. `None` when the model is `None`, `max_depth` is 0, or the owner has no level-1 row for that proposition. Speech acts pass `belief:<BeliefId.value>`. A `fact:` key does not select a `Tell`. Otherwise exactly one `EpistemicJudgment`:
  1. `CONTRADICTORY` when the level-1 row's `contradiction_mass` is at or above `contradiction_threshold`, or both a level-2 `KNOWS` or `BELIEVES` row and a level-2 `DOES_NOT_KNOW` row for that recipient and proposition are at or above `action_threshold`.
  2. `UNCERTAIN` when the owner's level-1 attitude is `UNCERTAIN` and contradiction is below the threshold.
  3. `ALREADY_KNOWN` when a level-2 `KNOWS` or `BELIEVES` row for that recipient is at or above `action_threshold` and no competing `DOES_NOT_KNOW` row is.
  4. `SECRET` when the level-1 row's `witness_ids` is empty and the recipient is modeled `DOES_NOT_KNOW` or has no positive level-2 row.
  5. `NEW` when the owner level-1 attitude is `KNOWS` or `BELIEVES`, `witness_ids` is non-empty, the recipient is absent from that set, and the recipient is `DOES_NOT_KNOW` or has no positive level-2 row.
  Precedence is the list order above. Secret is a judgment, not an `EpistemicAttitude`.
- **Communication hook.** In `DeterministicSocialMessagePolicy.select`, after `mind_message_hint` and before a belief `Tell` is committed, if the selected belief's `belief:` proposition ref yields a judgment for the chosen recipient:
  - `NEW`: keep the `Tell`.
  - `ALREADY_KNOWN` or `SECRET` or `CONTRADICTORY`: skip that belief and continue with the next selected belief or the later ask/talk fallback.
  - `UNCERTAIN`: skip the `Tell`. Copy `food`, `water`, `rest`, or `danger` only when `SemanticClaim.predicate` or a text `ClaimValue` is exactly one of those tokens, and emit `Ask` for that token with `source_basis` `UNREFERENCED`. Otherwise continue the existing fallback.
  - An empty attribution tuple, a `None` mind, or judgment `None` leaves today's utterance in place. Do not read `utterance.text`. Do not add a source-basis value. Do not bump `communication.v1`.
- **Flag off and depth 0.** `PASSTHROUGH` never calls `update_epistemic_state`. A `TheoryOfMind` with an empty attribution tuple does not change `select`. `derive_future_actions` and `update_theory_of_mind` both copy `attributions` on every `TheoryOfMind(...)` rebuild so a later epistemic update is not wiped and a hypothesis-only call leaves an existing ledger intact.
- **Checkpoint and trace.** Attributions ride inside `TheoryOfMind`, which is already an optional in-memory checkpoint field. Do not bump a checkpoint schema and do not add an Alembic revision. Do not add the ledger to `subjective-v1`. Trace projection stays on the existing theory-of-mind summary fields. Epistemic counts are DEBUG logs only.
- **Audit.** Add frozen `EpistemicAuditSnapshot` (attribution id, nesting level, attitude, source, quantized confidence, proposition ref). `MindAudit.epistemic` is a tuple of those snapshots, default empty. `build_mind_audit` fills it from `model.attributions`. `MindAudit.__post_init__` accepts only `EpistemicAuditSnapshot` in that tuple and still accepts only `MindHypothesisSnapshot` in `snapshots`. Same durability as the existing mind audit: in memory only, not written by runner-result serialization. No utterance text. Do not add an analysis metric module. Do not feed snapshots back into the loop.
- **Fail closed.** Unknown enums, owner mismatch, non-finite masses, a self id in `modeled_agents`, a chain length mismatch, depth above 3, and `DOES_NOT_KNOW` at level 1 raise `ValueError` with stable reason codes. A bad cue is dropped, not repaired from the world.

## Non-Goals

- Owning `multi_hop_testimony_tracking`, or keeping cues whose `hop_count` is greater than 1
- A recursive belief tree, a child-model field, or an updater that emits nesting above 2
- Rows meaning "Alice believes Bob believes Alice …"
- Reading or copying another agent's private cognition, including by widening `VisibleBody` or bystander `other_entity_id`
- Turning secret, uncertain, or contradictory into stored attitudes or new commands
- Adding an `AgentCommand`, a `CommunicationSourceBasis`, a capability flag, or a runner schema version
- Inserting a `CognitiveLoop` ordinal, bumping the cognition-trace schema, or adding an Alembic revision
- Writing epistemic rows into `SemanticBelief`, relationship revisions, the causal world model, or the self-model
- Letting LLM output choose or score an epistemic row
- Putting Experiment M on the V1 regression gate
- Enabling prospective, counterfactual, identity, emotion, or world-model flags as a side effect

## Commit Plan
- **Commit 1** (after tasks 1–3): `feat(cognition): add a bounded epistemic ledger to theory of mind`
- **Commit 2** (after tasks 4–6): `feat(cognition): choose speech acts from epistemic judgments`
- **Commit 3** (after tasks 7–8): `test(experiments): cover asymmetric knowledge and document the ledger`

## Tasks

### Phase 1: Ledger Contracts and the Enabled Update

- [x] Task 1: Add epistemic contracts and `EpistemicPolicy`.
  - Deliverable: frozen types in `src/agents/cognition/epistemic.py`, with the public types re-exported from `src/agents/cognition/__init__.py`. `TheoryOfMind` gains `attributions` defaulting to an empty tuple.
  - Types: `EpistemicAttitude` (`KNOWS`, `BELIEVES`, `UNCERTAIN`, `DOES_NOT_KNOW`), `EpistemicSource` (`SEMANTIC_BELIEF`, `OBSERVED_BEHAVIOR`, `COMMUNICATION`, `DERIVED`), `EpistemicJudgment` (`NEW`, `ALREADY_KNOWN`, `SECRET`, `UNCERTAIN`, `CONTRADICTORY`), `EpistemicAttribution` (owner id, proposition ref, optional belief id, modeled agent tuple, attitude, support, counter, confidence, `contradiction_mass` default `0`, source, nesting level, provenance ids, witness ids), `EpistemicPolicy` (`epistemic-model-v1`, prior `1`, knows threshold `0.8`, believes threshold `0.55`, contradiction threshold `0.5`, action threshold `0.55`, `max_depth` default `2`, hard ceiling `3`, `max_attributions` 64, `max_history` 32), `EpistemicDisclosure` (judgment, proposition ref, recipient id, attribution id or none, quantized confidence).
  - Attribution id is `ep-` plus sha256 of owner, nesting level, agent chain, attitude, and proposition ref. No RNG, wall clock, or Python `hash()`.
  - Constructors reject a recursive shape by not having one. They also reject depth outside `1..3`, a chain length other than `nesting_level - 1`, the owner inside `modeled_agents`, `DOES_NOT_KNOW` at level 1, empty proposition refs, non-finite masses, and unknown enums, with the reason codes in Design Decisions.
  - `epistemic.py` imports `TheoryOfMind`. `theory_of_mind.py` does not import `epistemic` at module level. `TheoryOfMind.__post_init__` validates `attributions` with a function-local import of `EpistemicAttribution`.
  - `TheoryOfMindPolicy` stays `theory-of-mind-v1`. Do not add epistemic knobs to runner JSON.
  - Logging: logger `agents.cognition.epistemic`. DEBUG on policy and row construction with owner id, policy version, nesting level, and attribution count. ERROR with field name and reason code on validation failure. No proposition values, utterance text, or another agent's belief masses at INFO. The unit test asserts those DEBUG and ERROR tokens.
  - Run `uv run ruff check` on every new or modified Python file in this task.
  - Files: `src/agents/cognition/epistemic.py`, `src/agents/cognition/theory_of_mind.py`, `src/agents/cognition/__init__.py`, `tests/unit/test_epistemic_model.py`.

- [x] Task 2: Implement the deterministic ledger update.
  - Deliverable: `update_epistemic_state(model, observation, beliefs, policy) -> TheoryOfMind` plus helpers for level-1 belief rows, co-presence `KNOWS`, explicit `DOES_NOT_KNOW`, and single-relation testimony.
  - Apply the depth, attitude, proposition-ref, confidence, witness, testimony, and cap rules in Design Decisions. The returned hypothesis tuple equals the input hypothesis tuple. `derive_future_actions` and `update_theory_of_mind` copy `attributions` unchanged on every `TheoryOfMind(...)` rebuild.
  - `max_depth == 0` returns the model with `attributions` unchanged and writes nothing new. Tests that need an empty ledger start from an empty tuple.
  - Level-1 rows come only from `BeliefActivationState.ACTIVE` heads. Copy `BeliefConfidenceState.confidence`. Store `contradiction_mass` on the row. Keep the row when that mass is at or above `0.5`, with attitude `UNCERTAIN`. `CANDIDATE` and `RETIRED` drop with `belief_inactive`. Refreshing a belief row unions `witness_ids` with new witnesses from this observation, cap 16.
  - Read epistemic testimony from `Observation.communications`. Do not read `MindCue`s. `_relation_atoms` still drops `knows`, `believes`, `uncertain`, and `does_not_know` with `nested_mind_rejected`.
  - The updater never returns a row with `nesting_level > 2`. A cue that would need a third agent is dropped with `epistemic_depth_exceeded`.
  - Parameter types are the owner's `Observation` and the owner's semantic belief sequence. Passing `WorldState`, `PhysicalRules`, `AgentBody`, or another agent's belief object raises `TypeError`. The module must not import `simulation`, `analysis`, `llm`, `world.events`, or `world._state`. It may import `world.observations`, `world.communications`, and owner-scoped memory belief types through the memory facade.
  - `hop_count > 1` drops with `multi_hop_deferred`. Nested non-epistemic predicates are not parsed into rows.
  - Logging: DEBUG per kept row with owner id, tick, attribution id, nesting level, attitude, source, and quantized confidence. INFO once per call with input belief count, created count, dropped count. WARNING when a cue is dropped, with reason code and no payload. ERROR on owner mismatch.
  - Depends on task 1.
  - Files: `src/agents/cognition/epistemic.py`, `src/agents/cognition/theory_of_mind.py`, `tests/unit/test_epistemic_model.py`.

- [x] Task 3: Run the ledger update from `prepare` when theory of mind is enabled.
  - Deliverable: `ENABLED` mode updates hypotheses, then the epistemic ledger, and carries both on the same `TheoryOfMind`. `PASSTHROUGH` still returns `None` before either call. Flag off does not change commands, boundary records, or checkpoints.
  - In `CognitiveLoop._prepare_theory_of_mind`, after `update_theory_of_mind` and before the model is returned, call `update_epistemic_state`. Beliefs are `memory.semantic_beliefs`. When that tuple is empty, use `loop_input.snapshot.semantic_beliefs`.
  - Add optional `epistemic_policy: EpistemicPolicy | None = None` on `CognitionLoopConfig` and on `CognitiveLoop` (`__slots__` and `__init__`). `CognitionLoopConfig.__post_init__` fills `default_epistemic_policy()` (`max_depth=2`) only when `theory_of_mind_mode` is `ENABLED` and the field is `None`. Passthrough leaves it `None`. `build_cognitive_loop` passes the field through. Add `epistemic_policy_version` to `condition_fingerprint_material`: `None` when the policy is absent, otherwise `epistemic-model-v1`. The runner does not grow a JSON key. `simulation.runner._cognition_config_for` keeps building `default_theory_of_mind_policy(allow_provider=False)` and leaves `epistemic_policy` unset so config post-init applies the default when the flag is on.
  - Abort and commit rules stay the ones already used for `TheoryOfMind`. Do not add a checkpoint field.
  - Logging: DEBUG `epistemic_prepare` with owner id, tick, mode, `max_depth`, and attribution count. DEBUG `epistemic_prepare_skipped` with `status=passthrough` or `status=depth_zero`. No rows at INFO. Logger `agents.cognition.loop`. The runtime test asserts those tokens.
  - Depends on tasks 1 and 2.
  - Files: `src/agents/cognition/loop.py`, `src/agents/cognition/configuration.py`, `src/simulation/runner.py`, `tests/unit/test_epistemic_model.py`, `tests/unit/test_theory_of_mind_runtime.py`, `tests/unit/test_cognition_configuration.py`.

### Phase 2: Disclosure and Communication

- [x] Task 4: Add the disclosure function.
  - Deliverable: `epistemic_disclosure` returns one judgment or `None` using the precedence in Design Decisions.
  - A `None` model, an empty ledger, depth 0, and a proposition the owner does not hold return `None`. Competing level-2 `KNOWS` and `DOES_NOT_KNOW` rows at or above threshold return `CONTRADICTORY`. A level-1 `contradiction_mass` at or above `0.5` returns `CONTRADICTORY` even when no level-2 row exists. `SECRET` requires an empty `witness_ids` tuple on that level-1 row. `NEW` requires a non-empty `witness_ids` tuple, recipient absent from it, and owner attitude `KNOWS` or `BELIEVES`. A `fact:` proposition ref does not select a `Tell`.
  - Logging: DEBUG `epistemic_disclosure` with owner id, recipient id, judgment, nesting level used, and quantized confidence. DEBUG `epistemic_disclosure_skipped` with reason `no_model`, `empty_ledger`, `depth_zero`, or `unknown_proposition`. No proposition payloads. Logger `agents.cognition.epistemic`. The unit test asserts those tokens and that utterance text is absent.
  - Depends on task 2.
  - Files: `src/agents/cognition/epistemic.py`, `tests/unit/test_epistemic_disclosure.py`.

- [x] Task 5: Use the judgment in `DeterministicSocialMessagePolicy.select`.
  - Deliverable: a mind with attributions can suppress or redirect a belief `Tell`. A mind with an empty attribution tuple, or judgment `None`, keeps today's utterances for the same fixture.
  - Apply the `NEW` / `ALREADY_KNOWN` / `SECRET` / `UNCERTAIN` / `CONTRADICTORY` table in Design Decisions to the selected belief before the tell is returned. The proposition ref is `belief:<BeliefId.value>`. Walk selected beliefs in their existing order. The first belief whose judgment is `NEW` or whose judgment is `None` still tells. For `UNCERTAIN`, copy `food`, `water`, `rest`, or `danger` only when `SemanticClaim.predicate` or a text `ClaimValue` is exactly one of those tokens, and emit `Ask`. Any other claim continues the existing fallback. Other blocking judgments skip that belief. Do not add enum members or schema versions.
  - Logging: DEBUG `epistemic_message` with owner id, tick, action kind, recipient id, judgment, and confidence band. DEBUG `epistemic_message_skipped` with reason `empty_ledger` or `status=skipped`. No utterance text. Logger `agents.cognition.communication`. The unit test asserts those tokens.
  - Depends on task 4.
  - Files: `src/agents/cognition/communication.py`, `tests/unit/test_epistemic_disclosure.py`.

- [x] Task 6: Add scenario tests for asymmetric knowledge and the depth cap.
  - Deliverable: deterministic scenarios, built from owner observations and owner beliefs only, cover each judgment and the nesting bound. No test reads another agent's belief store or mind.
  - Build real `SemanticBelief` heads (`BeliefActivationState.ACTIVE`) and owner observations. A class-object comparison is not a scenario.
  - Scenarios:
    - Alice's `ACTIVE` belief has confidence at or above `0.8` and a non-empty `witness_ids` that excludes Bob. Bob is visible now. Judgment toward Bob is `NEW`. `select` still returns `Tell` when that belief is selected. A later update unions witnesses; Bob stays absent from the set until he is actually witnessed.
    - Bob is in `witness_ids`. Level-2 attitude is `KNOWS`. Judgment is `ALREADY_KNOWN`. `select` does not `Tell` that belief.
    - Alice's level-1 belief row has empty `witness_ids`. Judgment is `SECRET`. `select` does not `Tell`.
    - Alice's copied confidence is below `0.55` and `contradiction_mass` is below `0.5`. Level-1 attitude is `UNCERTAIN`. When `claim.predicate` is `food`, `select` returns `Ask`. A claim whose predicate and text value are outside the allowlist does not ask from this path.
    - `contradiction_mass` at or above `0.5` still stores the level-1 row and yields `CONTRADICTORY` and no `Tell`. Both `KNOWS` and `DOES_NOT_KNOW` above threshold for Bob does the same.
    - Passing unit-interval `support_mass=1` and `contradiction_mass=0` with `confidence=0.8` stores confidence `0.8`, not `0.5`.
    - `CANDIDATE` and `RETIRED` heads produce no row (`belief_inactive`).
    - Flag off, or an empty attribution tuple, keeps the pre-ledger `Tell`.
    - Constructing `nesting_level=4` or a chain of length 3 raises `epistemic_depth_rejected`. `update_epistemic_state` with `max_depth=2` drops a would-be deeper cue and does not store a child row. A level-3 row constructed directly is rejected by the updater when `max_depth` is 2. `max_depth=0` leaves an existing ledger unchanged.
    - `hop_count > 1` on `Observation.communications` does not create a row.
  - Logging assertions: DEBUG lines for the judgment and WARNING lines for depth and multi-hop drops include reason codes and exclude utterance text.
  - Run `uv run ruff check` on `tests/unit/test_epistemic_asymmetry.py`.
  - Depends on tasks 2, 4, and 5.
  - Files: `tests/unit/test_epistemic_asymmetry.py`.

### Phase 3: Experiment Identity and Docs

- [x] Task 7: Register Experiment M and extend the in-memory mind audit.
  - Deliverable: `experiment_m_epistemic_asymmetry` in `src/experiments/catalog.py` with arms `m-disabled` and `m-enabled`. Both stay on `runner-config-v4`, share seed, scenario, and stochastic identity, and differ only by `advanced_social_inference`. The enabled arm is what turns the ledger on via the existing flag. Do not append Experiment M to `tests/unit/test_v1_regression_gate.py`.
  - Add `EpistemicAuditSnapshot`. `MindAudit.epistemic` defaults to an empty tuple. `build_mind_audit` fills it from `model.attributions`. `__post_init__` rejects any other type in that tuple. Nothing in cognition reads the audit back. Do not add `src/analysis/` metric code and do not serialize the audit into the runner result document. Export `experiment_m_epistemic_asymmetry` from `src/experiments/__init__.py` the same way as `experiment_l_theory_of_mind`.
  - The catalog test checks arm identity, schema version, shared stochastic identity, flag values, and absence from the V1 catalog list. Behavioral asymmetry stays in task 6.
  - Logging: DEBUG `experiment_m_built` with experiment id and condition id, matching `experiment_l_built`. DEBUG `epistemic_audit` with owner id, tick, and snapshot count. No proposition payloads. Loggers `experiments.catalog` and `agents.cognition.epistemic`.
  - Depends on task 3.
  - Files: `src/experiments/catalog.py`, `src/experiments/__init__.py`, `src/agents/cognition/theory_of_mind.py`, `src/agents/cognition/epistemic.py`, `tests/unit/test_epistemic_experiment.py`, `tests/unit/test_v1_regression_gate.py`.

- [x] Task 8: Document the bounded ledger.
  - Deliverable: cognition docs state that `advanced_social_inference` still owns a private first-order model, and that the same flag adds a flat epistemic ledger with `max_depth` default 2 and hard cap 3. They state the five communication judgments, that secret is not a stored attitude, that another agent's mind is never an input, and that Experiment M and `theory_of_mind@1` stay off the V1 regression gate. `multi_hop_testimony_tracking` remains unowned.
  - Update `docs/cognition-runtime.md`, `docs/architecture.md`, `docs/simulation-runner.md`, and the V2 seam paragraph in `.ai-factory/ARCHITECTURE.md`. Do not edit `.ai-factory/ROADMAP.md` in this task. Linkage lives in this plan.
  - Logging: none. This task changes documentation only.
  - Depends on tasks 5, 6, and 7.
  - Files: `docs/cognition-runtime.md`, `docs/architecture.md`, `docs/simulation-runner.md`, `.ai-factory/ARCHITECTURE.md`.
