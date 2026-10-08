# Implementation Plan: V3-14 Innovation and Bounded Experimentation

Branch: main (no new branch; `git.create_branches: false`)
Created: 2026-10-08
Improved: 2026-10-08 (`/aif-improve`)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage
Milestone: "M7 — V3 Generational Civilization"
Rationale: Deepens already-owned `cultural_historical_memory` so agents can propose bounded experiments whose objective outcomes, accidental discoveries, and later knowledge all stay provenance-linked without letting an LLM invent physics or treating one success as permanent know-how.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] mode=ultra treated as full (richer plan); remaining args describe the feature
INFO [aif-plan] resolved plan file: .ai-factory/plans/v3-14-innovation.md (format=slug)
INFO [aif-plan] plan name prefix v3- applied per user request; suggested stem `v3-14-innovation`; git.create_branches=false so stem is description slug (branch-derived naming disabled)
INFO [aif-plan] RESEARCH.md absent; research_influenced_plan=false
INFO [aif-plan] plan_default_milestone=auto would surface M6 first; scope is explicitly v3-14 under M7 so linkage uses M7
INFO [aif-improve] refined 2026-10-08: learn_into_genealogy on the experiment spec (v35 uptake keyset unchanged); experiment_resolved excluded from the independent-discovery scanner; prefixed law tokens item:/resource:/tool:; write-pair via checkpoint_schema_for_production plus accepted v15/v12; harm bands hunger_damage / attack_damage_min; no experiment RNG stream; occurrence public_facts for the five classes; memory via DirectObservationMemoryUpdateHook; METRIC_FAMILY_COUNT pin sweep; matrix_schema.py priority; causal debugger maps; experiment_hypothesis/v1 prompt package; ActionDirection unchanged

## Compatibility contract

This plan **deepens** already-owned **`V3CapabilityFlags.cultural_historical_memory`** (v3-09 through v3-13). It adds **bounded agent experimentation**: cognition may propose a closed hypothesis; `WorldEngine` alone classifies the objective result; a success is not knowledge until the agent remembers, repeats, and deliberately learns, teaches, or records it.

1. V1/V2 invariants intact. `WorldEngine` remains the only objective mutation authority. Agents receive immutable per-agent `Observation` / `Perspective` only. `WorldEvent` records remain immutable and append-only. Subjective state stays outside the objective fold. Godot remains read-only. Deterministic replay continues. No scripted `innovation_emerged` / `discovery_must_spread` / `experiment_succeeds` outcomes.
2. Flag ownership unchanged: keep `cultural_historical_memory`, `generational_population`, and `kinship_inheritance` owned. Do **not** own `multi_polity_migration`, `institutional_economy`, or `multi_hop_testimony_tracking`. **No new V3 capability flag.**
3. Flags-off / channel-off / experimentation-object-absent = prior baseline. With all V3 flags off, or with `cultural_historical_memory=False` / `cultural_feature_provenance` absent / `bounded_experimentation` absent, trajectories and `exact_trajectory_hash` match the pre-plan baseline for AE–AP where applicable. Existing genealogy / durable / repository / cultural metric families stay unchanged (sibling families only).
4. Schema bumps use accepted-set + exact key-set discipline. Never drop accepted V1/V2/V3 versions in the same change that adds a write version.
5. **LLM never invents objective physics (locked).** A model may only fill a closed hypothesis draft (operator, operand ids present in the current observation, a subjective predicted outcome). It cannot add laws, item kinds, damage numbers, products, success probabilities, or outcome classes that the engine must obey. Physics lives in a predeclared `ExperimentLawCatalog` read only by private world rules. Unlisted operand pairs resolve to `failure` with no novel product.
6. **Outcome authority (locked).** Closed objective classes, assigned only by `WorldEngine`: `success`, `partial_success`, `failure`, `harm`, `unexpected`. Cognition's predicted class is not an input to the law evaluator. `ActionOutcome` (`applied` / `not_applied`) stays the admission result; it is not these five classes.
7. **Success is not knowledge (locked).** An applied experiment does not mint a `PracticalKnowledgeEntry`, semantic belief, skill level, cultural feature, or society technique. The agent must observe, remember, and then explicitly learn, repeat under the learn gate, teach, or record. Default learn gate requires repeated matching objective outcomes (`repeat_threshold` default 2) plus `BoundedExperimentationSpec.learn_into_genealogy` and an active genealogy channel. Do **not** add a key to `KnowledgeGenealogyUptakeCompose` (exact v35 key set stays unchanged). Kind `experiment_resolved` is excluded from `apply_practical_knowledge_from_independent_discovery`.
8. **Accidental discovery (locked).** The engine sets `discovery_mode=accidental` only when `hypothesis_id` is empty, and `deliberate` when it is non-empty. Cognition may additionally mark the **trial** accidental when the event class is `unexpected` and the subjective prediction is missing or unequal. That overlay does not rewrite the event. Accidental trials still do not auto-become knowledge. Do **not** widen `KnowledgeTransmissionOrigin`; accidental vs deliberate is an experiment-ledger field copied into evidence refs only when a later learn/teach/record step runs.
9. **Provenance (locked).** Chain is `ExperimentHypothesis` → `ExperimentTrial` → authoritative `experiment_resolved` event id → owner episodic `MemoryTrace` → optional practical-knowledge `evidence_refs` (`evt:{id}`, `hypothesis:{id}`, `discovery_mode:{mode}`). Analysis may walk that chain. Live cognition never receives the law catalog or another agent's experiment ledger.
10. **No new item kinds.** Physical deltas are a closed set over the existing production catalog and existing harm/need primitives: `none`, `consume_operand`, `emit_catalog_product`, `partial_emit`, `apply_harm_band`. `emit_catalog_product` / `partial_emit` may name only products already in the run's `ProductionCatalog`.
11. **Preserve v3-02–v3-13 locks:** blank-slate deny-list includes the new ledger; closed Observation does not carry the law table or peer hypotheses; ELDER ≠ leader; related ≠ affection; no parent→caregiver hardwiring; no global Culture / LibraryInstitution / `GlobalTechniqueRegistry`; durable marks ≠ truth; historical layers stay analysis-only; Alembic head `0017`; kinship cultural inheritance handoff stays deferred; triple representation (objective capability ≠ subjective knowledge ≠ research lineage) stays intact.
12. **`api` must not import `analysis`.** Persist metric docs offline; serve via existing `MetricReadService` / inspection projections only.
13. Closed `AgentCommand` count becomes **35** (new `Experiment` only). SEMANTIC observer types become **54** (additive `EXPERIMENT_RESOLVED`). Protocol id stays `observer-protocol-v1`. Do **not** overload `knowledge_genealogy_*`, `skill_learning@1`, cultural, durable, or repository families.

## Goal

Let an agent **propose** a bounded experiment and let the world **decide** what happened, including surprises and harm, without writing the result into permanent knowledge until the agent does the later cognitive work.

Hypothesis shapes the agent may form (closed operator; operands are entity ids copied from the current observation, never free-text physics):

| Operator | Meaning |
| --- | --- |
| `combine` | Try operand A together with operand B |
| `apply_tool` | Use tool operand on resource operand |
| `vary_process` | Perform a closed process token (`harvest`, `craft`, `build`, `repair`, `store`) differently on one operand |

Objective classes the engine may return:

| Class | Meaning |
| --- | --- |
| `success` | Law matched and the predeclared full delta applied |
| `partial_success` | Law matched and only the predeclared partial delta applied |
| `failure` | No matching law, missing operand, or law class `failure` (no novel product) |
| `harm` | Law class `harm`; only a predeclared harm band on existing need/health primitives |
| `unexpected` | Law class `unexpected` with a predeclared side delta the agent did not have to predict |

After the engine commits an outcome, the agent may:

1. **Observe** the next-tick occurrence (actor always; co-located others only the public delta, not the hypothesis).
2. **Remember** an owner episodic trace correlated to the event id.
3. **Learn** only through the explicit learn gate into practical knowledge when `learn_into_genealogy` is on and the genealogy channel is active.
4. **Repeat** the same hypothesis; support/counter update from the objective class alone.
5. **Teach or record** through existing Tell / teaching and Inscribe / durable paths, citing the experiment event. The engine never auto-teaches or auto-inscribes.

Deliver:

- Exact optional root sibling `bounded_experimentation` on **`runner-config-v36`**
- World-owned `ExperimentLawCatalog` (private) and public outcome/operator enums
- Closed `Experiment` command, `experiment_resolved` event, write-pair `(EVENT_SCHEMA_REPLAY_V15, codec v12)` only when the channel is active
- Owner-scoped `ExperimentLedger` (hypotheses, trials, discovery mode) separate from `CausalHypothesis`, `MindHypothesis`, and `PracticalKnowledgeLedger`
- Optional genealogy uptake with provenance; accidental discovery retained on the trial even when uptake is off
- Analysis-only provenance query plus three sibling metric families
- Research UI Analytics discovery badges for the three families
- Off-gate Experiment AQ

## Design Decisions

### Invariant freeze (non-negotiable)

1. `WorldEngine` remains the only reader of experiment laws and the only writer of objective deltas and `experiment_resolved`.
2. Agents never receive the law catalog, another agent's ledger, or analysis provenance documents as facts.
3. `WorldEvent` records remain immutable; authoritative history stays append-only.
4. Subjective predictions may be wrong and never fold into objective replay identity.
5. Research provenance queries must not bias live cognition.
6. LLM output remains non-authoritative and cannot name a physical delta.
7. No scripted success, spread, or discovery booleans.
8. Godot remains read-only; this plan adds one semantic event type and does not add innovation-map chrome.
9. Runs remain reproducible (explicit seeds, deterministic law rows with no experiment RNG stream, deterministic fakes / recorded LLM paths).

### Scope split (locked)

| This plan (v3-14) | Deferred |
| --- | --- |
| Closed experiment command + law catalog + five outcome classes | Open-ended laboratory / technology-tier trees |
| Subjective hypothesis ledger + repeat support | Collapsing hypotheses into `CausalHypothesis` or semantic beliefs |
| Observe / remember / learn / teach / record as separate steps | Auto-uplift of every success into practical knowledge or skill level |
| Accidental discovery mode + provenance into genealogy evidence refs | New `KnowledgeTransmissionOrigin` value |
| `runner-config-v36` + write-pair v15/v12 when channel on | Alembic `0018+`; `/v2` HTTP; owning `institutional_economy` |
| Analysis provenance + three sibling metrics + Experiment AQ | Full interactive experiment browser in GraphsPanel |
| Optional LLM hypothesis **draft** inside closed enums | LLM-authored laws, products, or harm magnitudes |

**Rationale for cultural coupling:** v3-01 reserved innovation under `cultural_historical_memory`. Experimentation is how a private method can start; v3-13 genealogy is how it later becomes transferable know-how. The ledgers stay siblings. A trial is not a technique entry.

### Capability / ownership (locked)

1. **No new V3 flag.** Enabling experimentation requires already-owned `cultural_historical_memory=True` plus exact `cultural_feature_provenance` **and** exact `bounded_experimentation` on `runner-config-v36`.
2. **Prerequisite:** provenance required. `knowledge_genealogy`, `durable_records`, `knowledge_repositories`, production catalog, skill learning, and teaching modes are **optional**. Experimentation without genealogy is legal (observe/remember/repeat only; learn-into-knowledge skips).
3. **v35 without `bounded_experimentation`** stays valid (AP baseline). Schema `v36` always requires `bounded_experimentation` when that schema is selected.
4. Do **not** implement kinship knowledge inheritance handoff.
5. Other unowned V3 flags still fail closed.
6. When the experimentation object is absent: AE–AP bit-identity matches pre-plan for the same roster and seeds.
7. Do **not** claim that enabling experimentation auto-enables teaching, skill learning, durable records, or genealogy. Compose skips with DEBUG when the downstream channel is off.

### Flag × object gate matrix (locked)

| Config shape | Allowed? | Reject / notes |
| --- | --- | --- |
| Cultural flag off, experimentation absent | Yes (off) | Passthrough |
| Experimentation object present, cultural flag off | No | `bounded_experimentation_without_cultural_flag` |
| Experimentation object present, provenance absent | No | `bounded_experimentation_requires_cultural_provenance` |
| Experimentation object present on schema ≠ v36 | No | `bounded_experimentation_requires_v36` |
| Cultural + provenance on **v35**, experimentation absent | Yes | Pre-plan AP behavior |
| Cultural + provenance + experimentation on **v31..v35** | No | `bounded_experimentation_requires_v36` |
| Cultural + provenance + experimentation on **v36** | Yes | Experiment channel enabled |
| Schema `v36` without experimentation object | No | `v36_requires_bounded_experimentation` |
| Schema `v36` without provenance | No | `v36_requires_cultural_provenance` |
| Genealogy / durable / repository on **v36** (with experimentation) | Yes | Widen allowlists capped at v35 to include v36 |
| Experimentation `mode=disabled` present | No | `bounded_experimentation_mode_invalid` — omit object for off |
| Cultural-only on v36 (lifecycle off) + experimentation | Yes | Widen `_cultural_only` to include v36 |
| Genealogy on v36 without experimentation | No | `v36_requires_bounded_experimentation` |
| Empty law list | No | `bounded_experimentation_laws_empty` |
| Law product id absent from production catalog | No | `experiment_law_unknown_product` |
| Duplicate law key (operator + canonical operands) | No | `experiment_law_duplicate` |

### Runner schema (locked)

Introduce `RUNNER_SCHEMA_VERSION_V36 = "runner-config-v36"`:

- Exact root key set = **v35 accepted roots** ∪ sibling **`bounded_experimentation`** (genealogy / durable / repository keys remain optional).
- `bounded_experimentation` present ⇒ `schema_version == runner-config-v36` and cultural flag on with exact provenance.
- Decode v23–v35 synthesizes `bounded_experimentation=None`.
- Gate rewrite: `cultural_historical_memory=True` accepts `{v31..v36}`. Rewrite provenance / `_cultural_only` / historical / durable / repository / genealogy allowlists capped at v35 to include v36.
- Default write stays `runner-config-v4` when all V3 flags are off.
- **Write-pair bump only when the channel is active at run start:** `(EVENT_SCHEMA_REPLAY_V15, "v12")` beats the v14/v11 repository pair. Channel off keeps today's priority (repositories → durable → dependency care → kinship → init → lifecycle → artifacts → dynamics → production → replay-v5).
- **Matrix finalize (Task 13 only):** in `src/experiments/matrix_schema.py`, insert `bounded_experimentation_on` immediately before the current first branch `knowledge_genealogy_on` (v36 beats v35). Task 1 must **not** edit finalize priority.

### Serialization contract (locked)

Mirror the v35 helper pattern in `runner_serialization.py`:

- v36 root keys = v35 family helper ∪ `{bounded_experimentation}` minus optional objects that are absent
- Exact child keyset `_BOUNDED_EXPERIMENTATION_KEYS` and nested `_EXPERIMENT_LAW_KEYS`
- `_encode_bounded_experimentation` / `_decode_bounded_experimentation` with `_require_keys`
- Encode: `schema_version == V36` requires provenance + experimentation; genealogy/durable/repository/layers optional
- Decode: v23–v35 → `bounded_experimentation=None`
- DEBUG log present/absent and `law_count` on decode (no operand payloads)
- Reject forbidden aliases: `llm_physics`, `invented_product`, `true_experiment_outcome`, `auto_knowledge`, `society_laboratory`, `technology_tree`, `experiment_pack`, `discovery_forced`, `success_becomes_knowledge`

### Runtime channel flags (locked)

1. `bounded_experimentation_active = config.bounded_experimentation is not None` at run start.
2. Bind the **`BoundedExperimentationSpec`** into cognition loop kwargs (caps, repeat threshold, `learn_into_genealogy`, allow_provider). Bind the **law catalog** only into `WorldEngine` / private rules — never into `CognitiveLoop`.
3. Subjective checkpoint carry for `ExperimentLedger` follows the practical-knowledge pattern (owner-scoped, outside the objective fold, in-memory runtime checkpoint, no SQLAlchemy subjective table).
4. New agents: blank-slate denies copy of `experiment_ledger` (counts start empty).

### `BoundedExperimentationSpec` (locked)

Root sibling object; omit for off. Exact keys (reject extras / missing):

| Key | Type / values | Role |
| --- | --- | --- |
| `policy_id` | `bounded-experimentation-v1` only | Closed policy id |
| `max_hypotheses` | int 1..32 | Per-owner cap; eviction drops lowest support then oldest |
| `max_trials_per_tick` | int 1..4 | Extra proposals in a tick are not admitted |
| `repeat_threshold` | int 1..8, default 2 | Matching objective outcomes required before learn may mint knowledge |
| `learn_into_genealogy` | bool, default false | When true and genealogy is active, the learn gate may mint one entry. Absent from v35 uptake compose |
| `allow_provider` | bool, default false | LLM may draft a hypothesis; never a law |
| `laws` | non-empty tuple, max 64 | `ExperimentLaw` rows |

`ExperimentLaw` exact keys:

| Key | Type | Role |
| --- | --- | --- |
| `operator` | `combine` \| `apply_tool` \| `vary_process` | Closed |
| `operand_a_kind` | `item:{ItemKind}` \| `resource:{ResourceKind}` \| `tool:{ToolRole}` | Match key. Unprefixed tokens rejected |
| `operand_b_kind` | same prefixed set, or `none` for `vary_process` | Match key |
| `process_token` | `harvest` \| `craft` \| `build` \| `repair` \| `store` \| `none` | Required `none` unless operator is `vary_process` |
| `outcome_class` | the five classes | Engine result when the row matches |
| `delta` | `none` \| `consume_operand` \| `emit_catalog_product` \| `partial_emit` \| `apply_harm_band` | Predeclared physical effect |
| `product_id` | catalog product id or empty | Required non-empty iff delta emits a product |
| `harm_band` | `none` \| `minor` \| `serious` | Required non-`none` iff delta is `apply_harm_band` |
| `public_technique_token` | closed slug `tech:{token}` or empty | Optional label copied only at learn/teach/record time |

Match key = operator + prefixed operand kinds + process token. The command carries entity ids only. Private evaluation reads the live entity (`Item.kind`, `Resource.kind`, or `ToolMark.role`). A prefix that does not match that entity's type is `failure` + delta `none`. First match wins; builder rejects duplicates. No match ⇒ `failure` + delta `none`. One law row has one class. There is no experiment RNG stream and no sampled class.

Harm bands apply once to the **actor** using existing `PhysicalRules` scalars, with no new formula and no attack-range roll: `minor` = `hunger_damage` (default 2.0); `serious` = `attack_damage_min` (default 10). `harm_band=none` applies no health change.

### Models (locked)

Public world module `world/experimentation.py` (enums only; **no laws**):

- `ExperimentOperator`
- `ExperimentOutcomeClass`
- `ExperimentProcessToken`
- `ExperimentDeltaKind`
- `ExperimentHarmBand`
- `DiscoveryMode` (`deliberate`, `accidental`)

Private `world/_experiment_laws.py`:

- `ExperimentLaw`, `ExperimentLawCatalog`, `evaluate_experiment_law` — imported only from `world._rules` / `world._operations`

`world/actions.py`:

- `Experiment` command: `operator`, `operand_a_id`, `operand_b_id | None`, `process_token`, `hypothesis_id` (opaque string, max 64, pattern `[a-z0-9:_-]{1,64}`). No predicted outcome. No delta. Count **35**.
- `require_agent_command` accepts the new exact type.
- Lifecycle deny allowlist may include `"experiment"` as a concrete kind token. Do not deny it by default.

`world/events.py`:

- `ExperimentResolved`: actor, operator, operand ids, `outcome_class`, `delta` actually applied, `discovery_mode` as recorded by the engine from "hypothesis id present or absent" only (`deliberate` if `hypothesis_id` non-empty, `accidental` if empty). The engine does **not** read the subjective ledger to classify accident beyond empty hypothesis id. Cognition may additionally mark a trial accidental when prediction ≠ outcome and class is `unexpected` (subjective overlay; event stores the engine bit only).
- Kind literal `experiment_resolved`.

Cognition `agents/cognition/experimentation.py`:

- `ExperimentHypothesis`: owner, operator, operand ids, process token, `predicted_outcome` (subjective), support, counter, evidence event ids, active flag
- `ExperimentTrial`: hypothesis id or none, tick, event id, objective class, `discovery_mode`
- `ExperimentLedger`: owner-scoped hypotheses + trials
- `ExperimentAction`: non-authoritative compile input. `compile_experiment_command` returns one `Experiment` command or a stable reject code. It never returns a law or a product.

Hypothesis id = sha256 of owner, operator, canonical operand ids, process token. No RNG, wall clock, or Python `hash()`.

These types are not `CausalHypothesis`, `MindHypothesis`, `SemanticBelief`, or `PracticalKnowledgeEntry`. Updates must not call `revise_semantic_belief` or skill mutators.

### Cognition loop (locked)

1. **Propose.** Deterministic policy (`allow_provider=false` default) may open a hypothesis only from operand ids in the current observation and the three operators. Cap at one new hypothesis and one `Experiment` command per tick, inside `max_trials_per_tick`.
2. **LLM draft (optional).** When `allow_provider` is true, the provider returns only the closed draft schema (`llm/prompts/experiment_hypothesis/v1`). Reject unknown keys. Drop any key outside operator / operand ids / predicted outcome. Operand ids absent from the observation are rejected with `experiment_operand_not_observed`. The draft's `predicted_outcome` is stored on the hypothesis and **stripped** before `Experiment` is built.
3. **Admit.** The command enters the existing proposal → request → `WorldEngine` path. No side door.
4. **Resolve.** Private rules match laws, apply the closed delta or the failure delta, append `ExperimentResolved`.
5. **Observe.** Perception projects `experiment_resolved` onto the actor. Co-located agents see operand ids, outcome class, and public delta only — not `hypothesis_id` and not `predicted_outcome`.
6. **Remember.** Existing episodic formation may write one owner trace keyed by that event id. Do not open a semantic belief from the trace.
7. **Repeat.** Next ticks may re-issue the same hypothesis. Support increments when the objective class equals `predicted_outcome`; counter increments otherwise. Support is subjective and is not a probability the engine reads.
8. **Learn.** `commit_experiment_learning` runs only when all of the following hold: genealogy channel on, `learn_into_genealogy` is true, the hypothesis has at least `repeat_threshold` trials with the same objective class in `{success, partial_success, unexpected}`, and the caller is the owner ledger API (not the event applier). It calls a **new** helper that sets origin `independent_discovery` and the evidence refs listed above. It must **not** call `apply_practical_knowledge_from_independent_discovery` for this occurrence. That scanner must skip kind `experiment_resolved` even when `independent_discovery` compose is on. `failure` and `harm` never mint knowledge. One success with threshold 2 does not mint. `_KNOWLEDGE_GENEALOGY_UPTAKE_COMPOSE_KEYS` stays the v35 six-key set.
9. **Teach / record.** Existing teaching compose and `Inscribe` may cite `evt:{experiment_event_id}` only after the owner has a memory trace for that id. No automatic Tell or Inscribe inside the experiment resolver. If `public_technique_token` is empty, teach/record of a *method label* is skipped; the episodic trace may still exist.

### Accidental discovery (locked)

- Engine `discovery_mode=accidental` when `hypothesis_id` is empty (a command may still be admitted; the ledger records no hypothesis).
- Cognition sets trial `discovery_mode=accidental` when the event says `unexpected` and `predicted_outcome` is absent or unequal. This subjective bit does not rewrite the event.
- Analysis counts accidental trials from harvested trial audits, not from a second world graph.
- Accidental success still uses the learn gate. Provenance evidence includes `discovery_mode:accidental` only after learn.

### Analysis (locked)

Sibling families (catalog 65 → **68**):

| Family | Reads |
| --- | --- |
| `bounded_experiment_trials@1` | Trial counts by outcome class and operator |
| `bounded_experiment_discovery@1` | Deliberate vs accidental trial counts; unexpected share |
| `bounded_experiment_provenance@1` | Share of learned practical-knowledge entries whose evidence refs contain `evt:` from an experiment trial; zero when genealogy uptake is off |

DTOs are counts/histograms only. No law rows, no predicted text, no cognition feedback.

Researcher query (analysis-only): `knowledge_provenance_for_experiment(event_id)` → holder entry ids that cite that event, else empty. Never imported by cognition.

### Experiment AQ (locked)

Off the V1 gate. Profile id `bounded_experimentation@1`. Arms:

| Arm | Schema | Channel | Proves |
| --- | --- | --- | --- |
| `aq-channel-off` | v35 | absent | Hash matches pre-plan AP cultural+genealogy fixture |
| `aq-failure-unlisted` | v36 | on | Unlisted pair → `failure`, no new item kind |
| `aq-success-not-knowledge` | v36 | on, genealogy off or compose off | `success` event + memory trace; practical-knowledge entry count unchanged |
| `aq-repeat-then-learn` | v36 | on + `learn_into_genealogy` + genealogy | Below threshold: no entry; at threshold: one `independent_discovery` entry citing the event; scanner did not mint on the first `experiment_resolved` |
| `aq-harm` | v36 | on | `harm` class applies a predeclared band; no knowledge entry |
| `aq-unexpected-accidental` | v36 | on | `unexpected` without a matching prediction → accidental trial; still no auto knowledge |
| `aq-llm-cannot-invent` | v36 | on, `allow_provider` true with a fake | Extra physics keys rejected; command has no delta; outcome equals the law, not the fake |
| `aq-teach-record` | v36 | on + teaching or durable | Tell/Inscribe cites `evt:`; resolver itself emitted neither |
| `aq-flags-off` | v4 | absent | V3 flags off; hash stable |

Matrix allowlist includes AQ without enabling it on default batches.

### Architecture isolation (locked)

- `agents.cognition` may import `world.experimentation` enums and `Experiment` command. It must not import `world._experiment_laws`, `world._rules`, `world._operations`, or `analysis`.
- `llm` must not import world, simulation, or cognition.
- Analysis harvests detached audits only. It must not import cognition live ledgers or private world modules.
- `api` must not import `analysis` to compute these families.
- Forbidden alias strings rejected at decode.

### Docs (locked — mandatory)

Update:

- `docs/architecture.md` — seam row + Downstream V3 contract (v36, write-pair when channel on, command 35, no new flag, LLM non-authority)
- `docs/physical-simulation.md` — experiment command, law privacy, five outcome classes, no novel item kinds
- `docs/cognition-runtime.md` — hypothesis ledger, learn gate, accidental discovery, Observation omits laws and peer hypotheses
- `docs/analysis-metrics.md` — three families + provenance query
- `docs/llm-providers.md` — `experiment_hypothesis/v1` cannot carry physics
- `.ai-factory/DESCRIPTION.md` — V3 scaffolding blurb for v36
- `.ai-factory/ARCHITECTURE.md` — command count, semantic type count, owned-flag note
- `.ai-factory/ROADMAP.md` — M7 plans list + v3-14 sentence under cultural_historical_memory

Observer protocol string stays `observer-protocol-v1`. Document the additive semantic type in the architecture seam (no separate observer-chrome plan).

## Commit Plan

- **Commit 1** (after tasks 1–2): `feat(v3): add bounded_experimentation runner-config-v36 gates`
- **Commit 2** (after tasks 3–5): `feat(world): resolve Experiment commands with closed law outcomes`
- **Commit 3** (after tasks 6–8): `feat(cognition): experiment hypotheses observe remember and repeat`
- **Commit 4** (after tasks 9–11): `feat(cognition): learn teach and record experiment provenance`
- **Commit 5** (after tasks 12–14): `feat(analysis): experiment provenance metrics and Experiment AQ`

## Tasks

### Phase 1: Schema and world-private laws

- [x] Task 1: Add `RUNNER_SCHEMA_VERSION_V36`, `BoundedExperimentationSpec`, nested `ExperimentLaw` validation, `SimulationRunnerConfig.bounded_experimentation`, exact encode/decode, forbidden-alias frozenset, and the reject codes in the flag×object matrix. Rewrite cultural / historical / durable / repository / genealogy allowlists capped at v35 so v36 is accepted when the new object is present. Decode v23–v35 synthesizes `bounded_experimentation=None`. Do not edit matrix finalize priority (Task 13).
  - Deliverable: Round-trip tests; reject rows for missing provenance, v36 without the object, laws empty, duplicate law keys, unknown product ids, `mode=disabled`, and v35+experimentation; v35 genealogy-only still loads.
  - Files: `src/simulation/runner_models.py`, `src/simulation/runner_serialization.py`, `src/simulation/compatibility.py`, `tests/unit/test_bounded_experimentation_spec.py`
  - Logging: DEBUG decode with `present` and `law_count` only; INFO/raise stable reject codes; never log operand tokens or product payloads at INFO
  - Depends on: none

- [x] Task 2: Add public enums in `world/experimentation.py` and private `ExperimentLawCatalog.evaluate` in `world/_experiment_laws.py`. Operand kind tokens are prefixed: `item:{ItemKind}`, `resource:{ResourceKind}`, `tool:{ToolRole}`. Reject unprefixed tokens. Unlisted keys return `failure` + `none`. A prefix that does not match the live entity type (`Item.kind`, `Resource.kind`, or `ToolMark.role`) returns `failure` + `none`. Emit deltas only through the closed delta kind. Reject law rows that name a product outside the injected production catalog. No RNG stream. Export enums on the world facade; do not export the catalog.
  - Deliverable: Unit tests for prefixed match, unprefixed reject, type-mismatch failure, miss, duplicate rejection, harm-band requiredness, and product allowlist. Architecture test that `agents.cognition` and `llm` do not import `world._experiment_laws`.
  - Files: `src/world/experimentation.py`, `src/world/_experiment_laws.py`, `src/world/__init__.py`, `tests/unit/test_experiment_laws.py`, `tests/architecture/test_v3_experimentation_isolation.py`
  - Logging: DEBUG `experiment_law_matched` / `experiment_law_unlisted` with operator and outcome class; WARN on catalog build failure with reason code; no product blobs
  - Depends on: 1

<!-- Commit checkpoint: tasks 1–2 -->

### Phase 2: Command, admission, observation

- [x] Task 3: Add the `Experiment` command (35th `AgentCommand`), `require_agent_command` membership, and lifecycle deny-list token `"experiment"` without default-denying it. Compile path rejects predicted-outcome fields if a mapping is passed (`raw mappings are not agent commands` stays).
  - Deliverable: Command construction tests; count pin 35; unknown types still rejected.
  - Files: `src/world/actions.py`, `src/world/lifecycle_effects.py`, `tests/unit/test_experiment_command.py`
  - Logging: DEBUG `command_constructed tag=experiment` with operator only
  - Depends on: 2

- [x] Task 4: Admit `Experiment` in `world._operations` / `world._rules`. Resolve operands against current world state (present, actor-reachable under existing visibility rules) and read kinds from the live entity as in Task 2. Evaluate laws inside the engine. Apply only the law delta via existing item/need primitives. Harm: `minor` subtracts `PhysicalRules.hunger_damage` once from actor health; `serious` subtracts `PhysicalRules.attack_damage_min` once; no attack-range roll and no new damage formula. Append `ExperimentResolved`. Thread `bounded_experimentation_active` through `checkpoint_schema_for_production` (`src/simulation/persistence.py`), `select_checkpoint_schema` (`src/simulation/engine.py`), and the callers in `runner.py` and `service.py`. Select write-pair `(EVENT_SCHEMA_REPLAY_V15, codec v12)` when the channel is active at run start; leave priority unchanged when inactive. Add v15 to `ACCEPTED_EVENT_SCHEMA_VERSIONS` and `v12` to `ACCEPTED_PERSISTENCE_CODEC_VERSIONS` without dropping v2–v14 or codecs `v1`–`v11`. Replay round-trips the new event. Add `experiment` / `experiment_resolved` to the closed maps in `src/simulation/causal_debugger.py`. Channel-off trajectories stay on the previous write pair. Do not introduce an experiment RNG stream.
  - Deliverable: Engine tests for success, partial, failure, harm (both bands), unexpected, missing operand, prefix mismatch, and replay equality. Accepted-set tests still restore older schemas. Flags-off hash unchanged.
  - Files: `src/world/events.py`, `src/world/_operations.py`, `src/world/_rules.py`, `src/simulation/persistence.py`, `src/simulation/engine.py`, `src/simulation/runner.py`, `src/simulation/service.py`, `src/simulation/serialization.py`, `src/simulation/compatibility.py`, `src/simulation/causal_debugger.py`, `tests/unit/test_experiment_resolution.py`
  - Logging: INFO `experiment_resolved` with actor id, operator, outcome class, delta kind; DEBUG admission reject reason codes; never log law tables
  - Depends on: 3

- [x] Task 5: Project `experiment_resolved` in perception via `_public_facts_for_role` (`src/world/_perception.py`). Actor `public_facts` keys, closed: `outcome_class`, `delta`, `operator`, `discovery_mode`. Bystander keys: `outcome_class` and `delta` only. Map `success` / `partial_success` to `ObservedOccurrence.success=True`, `failure` / `harm` to `False`, and `unexpected` to `None`. Do not put `hypothesis_id`, predicted class, or law rows in `public_facts`. Nobody receives the law catalog. Add observer semantic type `EXPERIMENT_RESOLVED` (count 54) without renaming `observer-protocol-v1`.
  - Deliverable: Perception tests for actor vs bystander vs distant agent, the success-bool map, and the closed fact keys; semantic map pin 54.
  - Files: `src/world/observations.py`, `src/world/_perception.py`, `src/observer/version.py`, `tests/unit/test_experiment_perception.py`
  - Logging: DEBUG `experiment_occurrence_projected` with viewer role `actor|bystander` and outcome class
  - Depends on: 4

<!-- Commit checkpoint: tasks 3–5 -->

### Phase 3: Hypotheses, memory, repeat

- [x] Task 6: Add `ExperimentHypothesis`, `ExperimentTrial`, `ExperimentLedger`, id function, caps, and blank-slate deny-list entry `experiment_ledger`. Wire spec object into loop kwargs at initial build and mid-run admit. Do not bind the law catalog into the loop. Passthrough when the spec is absent (no ledger writes).
  - Deliverable: Model tests; blank-slate pin; runner kwargs test; AE–AP hash smoke when object absent.
  - Files: `src/agents/cognition/experimentation.py`, `src/agents/cognition/__init__.py`, `src/agents/cognition/loop.py`, `src/simulation/runner.py`, `src/simulation/new_agent_initialization.py`, `tests/unit/test_experiment_ledger.py`, `tests/unit/test_new_agent_blank_slate_guard.py`
  - Logging: DEBUG `experiment_ledger_constructed` with hypothesis_count; INFO `bounded_experimentation_enabled` with caps and `allow_provider`; DEBUG skip when absent
  - Depends on: 1

- [x] Task 7: Deterministic proposer plus optional `experiment_hypothesis/v1` structured draft. Default `allow_provider=false`. Add `src/llm/prompts/experiment_hypothesis/v1/{manifest.json,system.txt,user.txt}` and register it in `src/llm/prompts/loader.py`. Validator drops unknown keys and any physics/delta/product/probability field. Operand ids must appear in the current observation. Do **not** add an `ActionDirection` or `IntentionCode`. Compile one `Experiment` per tick the same way `agents/cognition/production.py` compiles `Harvest` / `Craft`: operands copied from the current observation. `compile_experiment_command` emits that command with hypothesis id set, or a stable reject. Predicted outcome stays on the hypothesis only.
  - Deliverable: Fake-LLM test that a payload containing `delta` and `product_id` is rejected and cannot change the engine outcome. Deterministic proposer test with no network. Test that `ActionDirection` membership is unchanged.
  - Files: `src/agents/cognition/experimentation.py`, `src/agents/cognition/production.py`, `src/llm/prompts/experiment_hypothesis/v1/manifest.json`, `src/llm/prompts/experiment_hypothesis/v1/system.txt`, `src/llm/prompts/experiment_hypothesis/v1/user.txt`, `src/llm/prompts/loader.py`, `tests/unit/test_experiment_hypothesis_draft.py`
  - Logging: INFO `experiment_hypothesis_proposed` with operator and id prefix; WARN `experiment_draft_rejected` with reason code; metadata-only LLM logs (no prompt body)
  - Depends on: 3, 6

- [x] Task 8: Keep `DirectObservationMemoryUpdateHook` in `src/agents/cognition/memory.py` as the only episodic writer. When kind is `experiment_resolved`, copy `outcome_class` and `discovery_mode` from actor `public_facts` into trace tags. Correlation stays `MemoryProvenance.observed_source_id`. Do not add a second memory writer, a semantic belief, or a skill update. Update support/counter on the matching hypothesis from the objective class versus `predicted_outcome`. Re-issuing the same hypothesis is allowed on later ticks until `max_trials_per_tick`.
  - Deliverable: Tests that one success leaves practical-knowledge and semantic-belief counts unchanged, that the trace tags include `outcome_class`, and that support/counter update.
  - Files: `src/agents/cognition/experimentation.py`, `src/agents/cognition/memory.py`, `src/agents/cognition/loop.py`, `tests/unit/test_experiment_remember_repeat.py`
  - Logging: DEBUG `experiment_remembered` with event id and outcome class; DEBUG `experiment_hypothesis_scored` with support and counter counts
  - Depends on: 5, 7

<!-- Commit checkpoint: tasks 6–8 -->

### Phase 4: Learn, teach, record, accident

- [x] Task 9: Implement `commit_experiment_learning` with `repeat_threshold`. Mint at most one `independent_discovery` practical-knowledge entry through a **new** helper when genealogy is on, `learn_into_genealogy` is true, and the repeated class is `success`, `partial_success`, or `unexpected`. Do not call `apply_practical_knowledge_from_independent_discovery` for this path. That function must skip kind `experiment_resolved` even when its `independent_discovery` compose flag is on. `failure` and `harm` never mint. Evidence refs carry event id, hypothesis id, and discovery mode. Do **not** add a key to `KnowledgeGenealogyUptakeCompose` or `_KNOWLEDGE_GENEALOGY_UPTAKE_COMPOSE_KEYS`.
  - Deliverable: Threshold tests (1 vs 2); genealogy-off and `learn_into_genealogy=false` skip; harm skip; evidence-ref assertions; v35 uptake key set unchanged; first `experiment_resolved` does not mint when only the old scanner is on.
  - Files: `src/agents/cognition/experimentation.py`, `src/agents/cognition/practical_knowledge.py`, `src/simulation/runner_models.py`, `tests/unit/test_experiment_learn_gate.py`
  - Logging: INFO `experiment_learned` with entry id and discovery mode when minted; DEBUG `experiment_learn_skipped` with reason code (`threshold`, `channel_off`, `class_ineligible`)
  - Depends on: 5, 8

- [x] Task 10: Accidental discovery. Empty `hypothesis_id` stores engine `accidental`. Subjective overlay marks `unexpected` trials accidental when prediction is missing or unequal, without rewriting the event. Accidental success still waits on Task 9's gate. Provenance query input is the trial audit, not a world-side knowledge object.
  - Deliverable: Tests for empty hypothesis id, mismatched prediction, and "no knowledge row until learn".
  - Files: `src/agents/cognition/experimentation.py`, `src/world/_rules.py`, `tests/unit/test_experiment_accidental.py`
  - Logging: INFO `experiment_discovery_mode` with `deliberate|accidental` and outcome class
  - Depends on: 4, 8

- [x] Task 11: Teach and record stay explicit. If the owner has a memory trace for the experiment event, existing teaching uptake and `Inscribe` may attach `evt:{id}`. The experiment resolver must not emit `Tell` or `Inscribe`. Skip method-label teach/record when `public_technique_token` is empty. Do not copy peer experiment ledgers.
  - Deliverable: Tests that resolution events exclude talk/inscribe kinds; a later chosen Tell/Inscribe cites the event; empty technique token skips the label and keeps the memory trace.
  - Files: `src/agents/cognition/experimentation.py`, teaching/inscribe compose call sites, `tests/unit/test_experiment_teach_record.py`
  - Logging: DEBUG `experiment_teach_cited` / `experiment_record_cited` with event id; DEBUG `experiment_label_skipped` when the token is empty
  - Depends on: 8, 9

<!-- Commit checkpoint: tasks 9–11 -->

### Phase 5: Analysis, experiment, docs

- [x] Task 12: Harvest detached experiment trial audits and practical-knowledge evidence refs. Add the three metric families and `knowledge_provenance_for_experiment`. Pin `METRIC_FAMILY_COUNT` to 68 in `src/analysis/specifications.py` and sweep every unit test that asserts `== 65` for that constant: `tests/unit/test_metric_specifications.py`, `test_knowledge_genealogy_metrics.py`, `test_v3_knowledge_genealogy_regression.py`, `test_v3_knowledge_repositories_regression.py`, `test_v3_durable_records_regression.py`, `test_mentorship_metrics.py`, `test_historical_memory_metrics.py`, `test_developmental_learning_metrics.py`, `test_dependency_care_metrics.py`, `test_cultural_narrative_metrics.py`, and `test_cultural_feature_metrics.py`. Families assemble only when the spec was present. No cognition import.
  - Deliverable: Known-answer metric tests; empty harvest when channel off; provenance query returns entry ids only after learn; no remaining `METRIC_FAMILY_COUNT == 65` pin.
  - Files: `src/analysis/experimentation.py`, `src/analysis/specifications.py`, `src/analysis/__init__.py`, `tests/unit/test_bounded_experiment_metrics.py`, and the pin files named above
  - Logging: DEBUG `experiment_metrics_assembled` with family ids and row counts; no trial payloads
  - Depends on: 9, 10

- [x] Task 13: Register off-gate Experiment AQ (`bounded_experimentation@1`) with the arms in the design section. In `src/experiments/matrix_schema.py`, insert `bounded_experimentation_on` immediately before the `knowledge_genealogy_on` branch (v36 beats v35). AQ stays off the V1 gate. Default batches do not enable it.
  - Deliverable: Catalog tests for each arm's assertion; V1 regression gate and `test_v2_scientific_invariants` green with V3 flags off.
  - Files: `src/experiments/catalog.py`, `src/experiments/matrix_schema.py`, `tests/unit/test_experiment_aq.py`
  - Logging: INFO experiment arm start with arm id and schema version; DEBUG channel active flag
  - Depends on: 4, 9, 11, 12

- [x] Task 14: Docs and pins listed in the Docs section. Research UI Analytics discovery badges for the three new families only (same pattern as genealogy badges; no new graph panel) in `clients/research-ui/src/epistemic.ts`, `clients/research-ui/src/views/AnalyticsPanel.svelte`, and `clients/research-ui/src/epistemic.test.ts`. Confirm Alembic head `0017`, protocol id unchanged, command count 35, semantic count 54. Run `ruff check` on the changed Python set before this commit.
  - Deliverable: Doc updates; UI badge test update; architecture isolation green; ruff clean on the changed set.
  - Files: `docs/architecture.md`, `docs/physical-simulation.md`, `docs/cognition-runtime.md`, `docs/analysis-metrics.md`, `docs/llm-providers.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/ROADMAP.md`, `clients/research-ui/src/epistemic.ts`, `clients/research-ui/src/views/AnalyticsPanel.svelte`, `clients/research-ui/src/epistemic.test.ts`
  - Logging: none in docs; UI remains free of law payloads and hypothesis text
  - Depends on: 12, 13

<!-- Commit checkpoint: tasks 12–14 -->
