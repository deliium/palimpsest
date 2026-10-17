# Implementation Plan: V3-24 Cultural Contact

Branch: main (current branch; `git.create_branches: false`)
Created: 2026-10-17
Mode: full (ultra depth requested)

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes — mandatory `/aif-docs` checkpoint during implementation.
- Artifact naming: every plan artifact produced for this feature begins `v3-`; canonical file is `.ai-factory/plans/v3-24-cultural-contact.md`.
- Implementation scope: optional objective contact recording when previously separated populations meet after cross-region migration or another supported cross-region relocation; analysis-only contact exposure, cultural convergence/continued divergence, hybrid practices, technology/knowledge transfer, lexical borrowing, story exchange, trade, communication, teaching, conflict, cooperation, reputation transfer, and cross-community kinship where the existing demographic model supports it. **No assimilation/multiculturalism/war/diplomacy policies, no Nation/Polity entity, no new capability flag, no new commands, no marriage/biology.**

## Roadmap Linkage
Milestone: "M7 — V3 Generational Civilization"
Rationale: Lets separately developed populations meet through the owned migration substrate and measures what changes afterward, without hard-coding assimilation, conflict, diplomacy, or convergence and without weakening WorldEngine authority or epistemic isolation.

INFO [aif-plan] using plan defaults from config: testing=yes logging=verbose docs=yes link_roadmap=true milestone=M7 — V3 Generational Civilization
INFO [aif-plan] full mode confirmed; git.create_branches=false; resolved plan file: .ai-factory/plans/v3-24-cultural-contact.md (format=slug)
INFO [aif-plan] plan_default_milestone=auto surfaces M6 first; explicit V3 scope uses M7, following v3-22/v3-23 precedent; this plan does not close M6
INFO [aif-plan] ultra request treated as full-mode depth; this skill has no separate ultra mode
INFO [aif-plan] RESEARCH.md absent and skill-context/aif-plan/SKILL.md contains context-budget rules only; research_influenced_plan=false
INFO [aif-plan] baseline selectors to recheck before implementation: 97 metric families, 43 commands, 72 observer semantic types, replay-v21/codec v19, runner-config-v44, Alembic 0017, Experiment AZ
INFO [aif-improve] refined v45 schema sweep, contact system-cause/transition contract, replay registration, contact memory/Godot presentation, collective-action attribution, pre/post window semantics, reputation channel filter, provenance wiring, and successful-Fled coverage; 18 tasks retained (Task 3a added)
INFO [aif-improve] post-completion refinement added Task 18 for stale simulation-runner, persistence, and Godot documentation; 19 tasks total, Task 18 completed

## Goal

Support the moment when previously separated populations meet again, and let researchers ask — after the run, from detached evidence only — whether contact was followed by cultural convergence, continued divergence, hybrid practices, knowledge transfer, lexical borrowing, reputation transfer, trade, cooperation, conflict, or cross-community kinship links. Existing mechanisms already provide migration, trade, communication, teaching, conflict, and cooperation; this plan adds only a neutral objective contact fact and the analytical layer that connects those mechanisms across candidate-community boundaries. Contact is never a group label, attitude, policy, or success condition.

## Current Implementation Evidence

- Regions and migration (v3-22, `runner-config-v44`, replay-v21/codec v19): `src/world/regions.py` immutable region/route/journey contracts; `src/world/_travel.py` deterministic arrivals; `JourneyStarted`/`JourneyArrived`/`JourneyEnded`; `src/experiments/regional_migration_scenario.py` / Experiment AY; `regional_population@1`, `regional_migration@1`, `regional_destination_beliefs@1`.
- Non-journey relocation is a separate path: a successful cross-region `Fled` is recorded as `Fled` by `src/world/_rules.py`, not as a `JourneyArrived`. A contact layer that only watches journeys would miss conflict-driven meetings.
- Candidate societies (v3-23): `src/analysis/society_emergence.py`, `society_divergence.py`, `society_isolation.py`; families `society_emergence@1`, `society_divergence@1`, `society_isolation@1`; `src/experiments/multiple_societies_scenario.py` / Experiment AZ; all off the V1 gate.
- Contact-enabling mechanisms already exist: `NegotiateExchange` / `ExchangeCompleted`; `Talk`/`Ask`/`Tell`; teaching relations plus `TeachingAudit`; `Attacked`; `Helped`; collective-project/public-good participation; `KinshipEdgeRecorded` with objective parent→child edges only. There is no marriage, mating, fertility, affinity, or spouse concept; forbidden kinship keys already reject those terms.
- Cultural and knowledge provenance already exists: `SubjectiveCulturalBelief` (`channel`, `parent_belief_ids`, `hop_index`, `mutated`, `recombined`, `evidence_refs`); `SubjectivePracticalKnowledge` (`origin`, `parent_entry_ids`, `source_agent_id`, `teacher_agent_id`); narrative `transmission_root_id`/carriers; terminology `NamingEvidenceItem.actor_id`; reputation `ReputationEvidenceItem.source_id`; kinship parent/child edges.
- Existing analysis rows: `SocietyDigestRow` (dimension/person/token, no tick); `society_emission_inputs_from_context` / `_from_snapshot`; `cultural_similarity@1`, `belief_convergence@1`, `semantic_naming_metrics`, `cultural_narrative_metrics`, `cultural_feature_metrics`, `knowledge_genealogy_*`, `mentorship_*`, `distributed_reputation@1`.
- Known composition gaps: society inputs are not wired into `MetricCollectionService` end-to-end; isolation evidence only harvests communication; trust is not auto-derived in the snapshot path; terminology and reputation ledgers have no detached export; practical-knowledge and teaching audits exist but are not joined to candidate communities.
- Baseline: 43 command variants, 72 observer semantic types, 97 metric families, Alembic `0017`, replay-v21/codec v19, runner-config-v44, latest experiments AY/AZ. `docs/analysis-metrics.md` still says 91 families; code is authoritative at 97. Recheck all selectors before implementation if other feature work lands first.

## Compatibility and Authority Contract

1. `WorldEngine` remains the sole objective mutation authority. The only new objective fact is a neutral `ContactRecorded` event emitted on a qualifying cross-region relocation (a completed journey arrival or a supported non-journey relocation such as a successful `Fled`). It records co-presence at a location; it is not a relationship, trust update, reputation claim, group identity, policy decision, or migration label.
2. No new capability flag. Contact is an optional sibling mode under the owned `multi_polity_migration` substrate and requires `regions_migration`. It does **not** require `cultural_historical_memory`; without cultural/economic/kinship channels, the corresponding contact dimensions are `absent`. Enabling contact never creates a polity, citizenship, border, assimilation rule, war, diplomacy, or group attitude.
3. No new commands. The closed `AgentCommand` count stays **43**. The new event is engine-emitted and may be perceived by the participants and the living agents already present; it does not add an action.
4. `runner-config-v45` is required only when `cultural_contact` is present. Exact keyset: v44 keyset plus the required sibling `cultural_contact` object with exact key `mode` (`disabled` or `deterministic`). Contact requires regions/migration; contact on pre-v45, v45 without contact, v45 without regions, or contact without the migration flag rejects with stable safe reason codes. Absent contact keeps the prior highest-active schema; default writes remain `runner-config-v4`.
5. Contact-active runs use exactly `(EVENT_SCHEMA_REPLAY_V22, "v20")`. Codec v20 carries v19 snapshot payloads and contact event details; it adds no contact state to snapshots. Contact-off regional runs keep `(21, "v19")`. Older schemas reject contact payloads; newer payloads stay unreadable under older schemas.
6. Contact is descriptive, not causal or normative. Convergence and continued divergence are both valid results. No threshold defines successful assimilation, multiculturalism, war, diplomacy, cooperation, or integration. No analysis result feeds cognition, memory, prompts, admission, or observations.
7. Intermarriage is **not** modeled. The demographic model has no spouse/mate/fertility/affinity edges and this plan does not add them. Cross-community kinship is reported only from existing objective parent→child `KinshipEdgeRecorded` edges, including mid-run admission links when `KinshipAdmitLinkPolicy` supports them; otherwise the kinship dimension is `absent`, never fabricated.
8. Analysis stays read-only and detached. New analysis modules import no persistence, no runtime, no world private modules, and no subjective ledger types; `src/experiments/composition.py` performs all joins from detached rows. The existing one-hop testimony limit remains; `multi_hop_testimony_tracking` stays fail-closed.
9. Contact analytics use opaque IDs and digest tokens only. Logs never contain narrative text, label text, propositions, prompts, message bodies, or reputation payloads. Contact public facts omit origin-region identity; the objective event retains region IDs for analysis only.
10. Keep Alembic `0017`, `/v1`, `observer-protocol-v1`, and the Godot layout. The observer semantic type count rises from 72 to **73** (`CONTACT_RECORDED`); command count stays 43; metric family count rises from 97 to **103**.
11. Existing V1/V2/V3 flags-off behavior is byte-identical: no contact events, no observation fields, no RNG consumption, no new IDs, no trajectory changes. Owned V2/V3 flags remain independently optional.

## Design Decisions

### Neutral contact recording

- New `src/world/contact.py` owns `ContactMode` (`disabled`/`deterministic`) and `CulturalContactSpec` with exact key `mode`. New `ContactRecorded` detail in `src/world/events.py` owns closed `relocation_kind` (`journey_arrived`, `fled`, or `move`), optional `journey_id` (present only for `journey_arrived`), `location_id`, `participant_ids`, `present_ids`, `origin_region_id`, `destination_region_id`.
- Emit at most one `ContactRecorded` per qualifying cross-region relocation, using one shared helper so the journey and non-journey paths cannot drift. For a journey, emit after `JourneyArrived` has placed the participants; for a successful non-journey relocation such as `Fled`, emit after the relocation is committed. All of these must hold: contact mode is deterministic; destination has at least one living non-participant; destination and origin regions are assigned and differ. Same-region relocations, empty destinations, failed/waiting/timeout journeys, failed flee, and contact-disabled runs emit nothing.
- `participant_ids` and `present_ids` are sorted, nonempty, disjoint, and reference living bodies at that boundary. Arrival processing order remains `(due_tick, journey_id)`; the present set includes earlier arrivals at the same location in the same tick. No partial group arrival and no contact event for a journey that ends at origin.
- Contact events have no state effect in replay: they validate and project as a no-op event while remaining available as prior committed evidence for perception and analysis. No snapshot state, no contact index, no Alembic migration.
- Agents do not know candidate communities. Contact public facts contain only the location and the two ID sets; origin region is omitted. Perception exposes the occurrence to participants and present agents only, allowing normal memory formation without any new attitude, trust, or reputation rule.

### Contact exposure and interaction mix

- New analysis module `src/analysis/society_contact.py`. Inputs are detached: candidate communities, optional observed contact episodes, per-tick location presence rows, closed interaction rows, and cross-community kinship rows. It derives contact onset per community pair, contact/location-tick counts, cross-community person-ticks, and interaction counts.
- `ContactPresenceRow(person_id, location_id, tick)` is folded from detached regional evidence: initial placements plus ordered relocations, entries, and deaths. A journey occupies its origin until `JourneyArrived`; a timeout is not an arrival. Presence is derived independently of contact events, so analytics still work on v44 runs without the contact channel.
- Interaction kinds are closed and mapped from existing evidence: `communication` (`Talked`/`Asked`/`Told`), `exchange` (`ExchangeCompleted`), `teaching` (`TeachingAudit` teacher/learner), dyadic `cooperation` (`Helped`), `conflict` (`Attacked`; `Fled` is reported separately as avoidance, not as war), and `kinship` (`KinshipEdgeRecorded`). `ProjectContributed` and `PublicGoodMaintained` are not dyadic; report them as separate `collective_project_contribution_count` / `public_good_maintenance_count` values only when project or public-good participation spans communities, with unpaired collective acts exposed as coverage rather than counted as contact cooperation. No new interaction semantics.
- Cross-community counts require two distinct candidate communities. Singleton/unassigned persons and same-community interactions are excluded from cross counts and surfaced as coverage gaps. No "native/foreigner", "ally/enemy", or group-morality label is created.

### Cultural convergence and continued divergence

- New analysis module `src/analysis/contact_cultural_change.py`. Add `ContactDigestRow(dimension, person_id, token, tick)` so the existing seven dimensions can be split into exact pre-contact (`tick < onset`) and post-contact (`onset <= tick <= final_tick`) windows per community pair. Contact onset is the earliest observed cross-community contact tick or, when events are absent, the earliest derived cross-community co-presence tick.
- For each pair and dimension, use one shared token universe across both windows so a token absent in one window is a real zero, not a different normalization. Compute pre-contact and post-contact Jensen-Shannon divergence with the existing `analysis.numerical.jensen_shannon_divergence` helper. Report `{dim}_pre_contact_divergence`, `{dim}_post_contact_divergence`, `{dim}_convergence_delta` (pre minus post; positive means observed convergence), `{dim}_converging_pair_count`, `{dim}_continued_divergence_pair_count`, and coverage counts.
- Pre-contact rows for a final community pair use the final member IDs, with `membership_stability` exposed as the share of members assigned to the same community at onset. When stability is low, the pair remains reportable but must not be described as community-level convergence. A positive delta is an observation, not proof that contact caused convergence. The document uses the notes code `descriptive_contact_association`; the BA contrast provides comparative evidence but no causal claim. Missing pre/post windows or channels stay `absent`/`partial`, never zero.

### Hybrid practices

- New analysis module `src/analysis/contact_hybrid_practice.py`. Hybrid evidence comes from existing lineage: practical-knowledge entries with `origin=combination` whose owner-local parents resolve to different candidate communities; cultural-feature beliefs with `recombined=True` when parent provenance resolves to multiple communities; narrative variants sharing a transmission root across communities; and convention/naming merges across communities.
- Report `hybrid_practical_knowledge_count`, `intercommunity_combination_count`, `hybrid_cultural_belief_count`, `narrative_shared_root_pair_count`, `narrative_merge_count`, `hybridization_rate`, and `unresolved_lineage_count`. Unresolved parent provenance is counted as unresolved, never as a hybrid. A hybrid form is not a "better" or "assimilated" culture.

### Knowledge transfer, lexical borrowing, and reputation transfer

- New `contact_knowledge_transfer@1` module consumes `PracticalKnowledgeAudit` rows and teaching audits. Donor community is resolved from `teacher_agent_id`/`source_agent_id`; recipient is the owner. Report total and per-channel transfer counts (`teaching`, `imitation`, `written_record`, `reconstruction`, `combination`), donor→recipient pair count, mutated-transfer count, mean hop, fingerprint-distance/fidelity aggregates, and unresolved-donor count. Technology exchange is practical knowledge/production technique, not a scripted technology tree.
- New `contact_lexical_borrowing@1` module consumes metadata-only naming evidence rows: owner, label token, referent kind, actor (speaker), channel, first/last binding tick, transmission, and lineage reference. A borrowing is a communicated evidence item whose actor belongs to a different candidate community. Report borrowed-label count, borrowing-event count, donor→recipient pairs, new adoption versus reinforcement/merge/competition, mean binding strength, and unresolved-actor count. Labels remain owner-scoped; no shared lexicon is created.
- New `contact_reputation_transfer@1` module consumes detached reputation evidence rows: owner, target, source, dimension, channel, trust band, tick. A transfer is only a `communication` or `third_party_story` evidence item whose source community differs from the owner community and whose source is not the target; direct observation and remembered interaction are first-hand evidence, not transfer. Report transfer events, donor→recipient pairs, target count, per-dimension counts, channel counts, trust-band counts, unresolved-source count, and non-transfer direct/remembered coverage. It does not aggregate a group reputation or write a mean back to any owner.
- Story exchange is represented by shared narrative transmission roots and cross-community narrative merges; no narrative text enters metrics or logs. Trade, communication, teaching, conflict, and cooperation remain existing objective events; the contact layer only conditions their counts on candidate-community pairs.

### Kinship boundary

- No intermarriage mechanism. The only supported cross-population kinship evidence is an objective parent→child edge, including an edge created at mid-run admission when `kinship_inheritance` and `KinshipAdmitLinkPolicy` allow it. `society_contact@1` reports `cross_community_kinship_edge_count` and pair coverage; when kinship is disabled, the value is absent with a safe reason.
- The BA kinship arm uses only supported admission-link behavior. If the policy cannot create a cross-community edge, the arm asserts `kinship_genealogy`/contact-kinship availability is absent rather than inventing a spouse or parent. No affection, trust, loyalty, obligation, inheritance right, clan, dynasty, spouse, mate, sex, fertility, or pregnancy field is introduced.

### Experiment BA (off the V1 regression gate)

- New `src/experiments/cultural_contact_scenario.py` plus catalog builder `experiment_ba_cultural_contact`. Register `cultural_contact@1` and add it to `OFF_GATE_MATRIX_EXPERIMENT_IDS`, following AY/AZ.
- Use at least two region-separated populations and owned cultural/economic channels (naming, norms, conventions, narratives, cultural provenance, practical knowledge/teaching, exchange, collective projects/public goods; kinship optional). Arms: `ba-channel-off` (v4 baseline), `ba-isolated`, `ba-contact-trade`, `ba-contact-teaching`, `ba-contact-conflict-cooperation`, and `ba-contact-kinship` (or an explicit absent-kinship assertion).
- Diagnostic command sequences are contract fixtures that exercise the analytics; at least one arm remains cognition-driven through normal perception/cognition. The arbiter asserts only structural facts: contact events exist in contact arms and not isolated/off arms; six contact families are present with coverage; cross-community trade/teaching/conflict/cooperation counts match their evidence; kinship availability is explicit; no unexplained cross-community transmission without a journey. It never asserts that convergence, assimilation, war, or cooperation "succeeded".

### Presentation and documentation

- Observer: add `CONTACT_RECORDED` to the closed semantic list, a presentation label, and the Godot known-type/router/log mappings; public facts expose location and participant/present IDs only. No protocol/layout rename, no Godot write authority.
- Memory: keep contact occurrence memory meaningful without inventing relationship state. `build_direct_observation_memory_trace` gains a bounded, deterministic contact projection that stores sorted participant/present IDs (capped, IDs only, no content) so an agent remembers who it met, not merely that a contact happened.
- Research UI: new `ContactPanel.svelte` under existing `research_inference` chrome with the `analytical_inference` epistemic class. It reads the generic metric endpoints; no new API route and no content payloads.
- Docs: `docs/experiments.md` (Experiment BA), `docs/analysis-metrics.md` (six families), `docs/architecture.md` (contact boundary/counts/replay pair), `docs/configuration.md` (v45 contact keys), `docs/observer.md` (contact semantic event), `docs/research-ui.md` (Contact view), `docs/physical-simulation.md` (arrival/relocation contact ordering), `docs/social-communication.md` (transfer/borrowing/reputation semantics), `docs/development.md` (verification), README index as needed.

## Commit Plan

Commit messages are suggestions for implementation; this planning command creates no commits.

- **Commit 1** (tasks 1–2): `feat(v3): add exact cultural-contact contracts and runner-config-v45`
- **Commit 2** (tasks 3, 3a–5): `feat(v3): record and present neutral cross-region contact`
- **Commit 3** (tasks 6–8): `feat(v3): analyze contact exposure, cultural change, and hybrid practices`
- **Commit 4** (tasks 9–13): `feat(v3): measure knowledge, lexical, and reputation transfer`
- **Commit 5** (tasks 14–15): `feat(v3): add Experiment BA and contact research view`
- **Commit 6** (tasks 16–17): `feat(v3): document and reconcile cultural-contact gates`

## Tasks

### Phase 1 — Contracts and configuration

- [x] **Task 1: Define the neutral contact contract with exact validation.**
  - Files: create `src/world/contact.py`; update `src/world/events.py`, `src/world/__init__.py`; create `tests/unit/test_contact_contracts.py`.
  - Deliver `ContactMode` (`disabled`/`deterministic`) and `CulturalContactSpec` with exact key `mode` only. Deliver `ContactRecorded` with closed `relocation_kind` (`journey_arrived`/`fled`/`move`), optional stable `journey_id` present only for `journey_arrived`, `EntityId` location/participant/present IDs, assigned origin/destination region IDs, sorted unique nonempty disjoint ID sets, and no group/attitude/policy fields. Reject unknown keys/kinds, missing/extra `journey_id` for the kind, empty sets, duplicates, overlap, equal regions, and malformed IDs with stable reason codes.
  - Acceptance: frozen contract round-trips; caller mutation cannot alter it; same-region or empty-present constructions reject; journey/flee variants round-trip without inventing a journey id on flee; no `Contact`/`Community` authority entity is created.
  - Logging: DEBUG at validation boundaries with counts and safe reason codes only; never region labels or participant content. Pure constructors need no side-effect logs.
  - Dependencies: none.

- [x] **Task 2: Gate and serialize `runner-config-v45`.**
  - Files: `src/simulation/runner_models.py`, `runner_serialization.py`, `runner.py`, `compatibility.py`, `matrix_schema.py`, `__init__.py`; create `tests/unit/test_runner_config_v45.py`; update `tests/unit/test_v3_flag_defaults.py`, `test_compatibility_matrix.py`.
  - Add exact `cultural_contact` sibling and v45 selector: v45 requires `regions_migration` + `multi_polity_migration` + `cultural_contact`; contact on pre-v45, contact without migration, v45 without contact/regions, and unknown/null nested keys reject. `mode=disabled` is accepted but emits no contact behavior; absent contact keeps v44 or the prior highest-active schema. No new capability flag.
  - **Schema sweep (required):** update every existing v44 gate and schema set so v45 is legal: `SimulationRunnerConfig` `regions_migration` validation (`runner_models.py:8024-8053` currently accepts v44 only), `public_goods`/`collective_projects` schema sets, `regions_migration` encode/decode branches, `_v45_family_root_keys` derived from `_v44_family_root_keys` plus `cultural_contact`, `compatibility.py`, and `matrix_schema.py`. Do not make v45 imply public goods or collective projects; it is the v44 family root plus the required contact sibling.
  - Acceptance: v1–v44 keysets and selectors unchanged; contact-off default writes remain v4; regions-only v44 stays valid; v45 round-trips in runner config and matrix schema with each legal prior channel (including public goods and collective projects); all owned/unowned flag gates remain fail-closed.
  - Logging: INFO at activation with schema/mode; DEBUG gate decisions; WARN invalid combinations with code only. No config dumps.
  - Dependencies: 1.

### Phase 2 — Engine, replay, and perception

- [x] **Task 3: Emit contact events on qualifying cross-region journey arrivals.**
  - Files: `src/world/_travel.py`, `src/world/_state.py` if validation requires it, `src/simulation/engine.py`; create `tests/unit/test_contact_arrivals.py`.
  - After a successful `JourneyArrived` placement, emit one `ContactRecorded` when contact is deterministic, origin/destination regions are assigned and differ, and at least one living non-participant is present. Use canonical `(due_tick, journey_id)` order and include earlier same-tick arrivals in the present set. Extend the journey transition stream (or an equivalent ordered result) so the contact event follows its arrival deterministically; `_prepare_journey_events` must allocate a unique system cause/ordinal for it and build the occurrence context at the destination. Reuse the existing `SystemEffectFamily.TRAVEL` family with a distinct ordinal; do not add a new system effect family. Emit nothing for same-region arrivals, empty destinations, timeout/death cancellation, failed starts, or contact-off runs.
  - Acceptance: known-answer two-region arrivals produce exact participant/present sets; a group arrival produces one event; same-tick ordering, event sequence, and system-cause ordinals are pinned; no event is emitted for a journey that ends at origin; contact-off trajectories and events are byte-identical to v44; no state index or RNG consumption is added.
  - Logging: DEBUG admission/visibility counts and reason codes; INFO committed contact summary at commit boundary (event count, community-pair count only); no region labels or body content.
  - Dependencies: 1, 2.

- [x] **Task 3a: Cover successful non-journey cross-region relocations.**
  - Files: `src/world/_rules.py`, `src/simulation/engine.py`, `src/world/events.py` if the existing detail shape requires it; create `tests/unit/test_contact_relocations.py`.
  - Route successful cross-region `Fled` (and any other non-journey relocation path confirmed during implementation) through the same contact-emission helper as Task 3. Emit after the relocation is committed, using destination presence and the same living/disjoint/cross-region rules; set `relocation_kind` to the correct closed value and omit `journey_id` for non-journey relocations. Do not create a second contact semantic or change `Fled` authority. Same-region flee, failed flee, empty destination, and contact-off runs emit nothing.
  - Acceptance: a successful cross-region flee into an occupied location produces exactly one `ContactRecorded`; failed/same-region flee does not; contact-off behavior is byte-identical; event ordering and cause identity are pinned for both action-derived and system-derived paths.
  - Logging: DEBUG relocation/contact counts and reason codes; INFO committed summary; no body/location content.
  - Dependencies: 3.

- [x] **Task 4: Carry contact events through replay, persistence, and compatibility.**
  - Files: `src/world/events.py`, `src/world/_replay.py`, `src/simulation/serialization.py`, `persistence.py`, `journal.py`, `replay.py`, `compatibility.py`, `matrix_schema.py`; create `tests/unit/test_contact_events.py`, `test_contact_checkpoint.py`; update `tests/unit/test_regional_travel_checkpoint.py`, `test_regional_travel_replay.py`, `test_regional_travel_events.py`.
  - Register replay-v22 and codec `v20` for contact-active runs. Encode/decode the closed event details; project the event as a validated no-op without adding snapshot state. **Exact registration points:** `EventDetails` / `_DETAIL_TYPES` / a `_CONTACT_DETAIL_TYPES` set, `_DETAIL_SCHEMAS`/supported-schema sets, `_payload_effect_complete`, `target_id_for_details`, `event_is_replayable`/`require_replayable_event`, `_apply_event` no-op branch, `REPLAYABLE_EVENT_SCHEMA_VERSIONS`, and `SUPPORTED_EVENT_SCHEMA_VERSIONS`. Preserve v19 snapshot payloads and v21/v19 regional behavior when contact is off. Reject contact details under older schemas and reject newer payloads under older codecs.
  - Acceptance: `event_is_replayable(ContactRecorded) is True`; every event prefix projects; contact events survive journal/snapshot round trips; restore/resume/fork preserve the same future observations; contact-off checkpoint pairs stay `(21, "v19")`; no Alembic migration and head stays `0017`.
  - Logging: DEBUG codec/projection counts and schema; ERROR safe validation codes only. Never log event bodies or full exported records.
  - Dependencies: 3, 3a.

- [x] **Task 5: Expose contact only to participants and present agents.**
  - Files: `src/world/_perception.py`, `src/world/observations.py` if a closed occurrence shape is needed, `src/agents/cognition/memory.py`, `src/observer/version.py`, `src/observer/adapt.py`/`project.py`, `src/api/observer_schemas.py` if serialization requires it, `src/observer/research_ui_state.py`, `clients/godot-observer/scripts/protocol/models.gd`, `event_router.gd`, `scripts/ui/event_log.gd`; create `tests/unit/test_contact_perception.py`, `test_contact_observer.py`, `test_contact_memory.py`; update semantic-count pins and the registered Godot suite.
  - Add `CONTACT_RECORDED` as semantic type 73, a presentation label, and a `SEMANTIC_TYPE_BY_KIND["contact_recorded"]` mapping. Perception projects an `ObservedOccurrence` to participants and present agents only, with `location_id` and sorted participant/present IDs; origin region is omitted. Non-present/non-participant agents receive nothing. Extend `build_direct_observation_memory_trace` with a bounded contact projection: sorted participant/present entity mentions, deterministic cap, IDs only, no content, so an agent remembers who it met rather than only that contact happened. Register the type in Godot `KNOWN_TYPES`, event routing/log labels, and tests; unknown-type fallback alone is not sufficient for a presented mechanism. No relationship, trust, or reputation mutation is added.
  - Acceptance: contact public facts match the event for allowed observers and are absent for others; contact memory contains the bounded participant/present IDs and survives live/restored parity; contact-off observation wire is unchanged; semantic count pins move 72 → 73; observer protocol/layout names stay unchanged; registered Godot suite passes.
  - Logging: DEBUG projection/memory counts/owner IDs/field presence; no observations, region labels, or content. INFO once per projection batch with counts only.
  - Dependencies: 3, 3a, 4.

### Phase 3 — Analysis modules

- [x] **Task 6: Implement contact exposure, interaction mix, and cross-community kinship.**
  - Files: create `src/analysis/society_contact.py`; update `src/analysis/__init__.py`; create `tests/unit/test_society_contact.py`.
  - Add frozen `ContactEpisodeRow`, `ContactPresenceRow`, `ContactInteractionRow`, `ContactKinshipRow`, `ContactPairRow`, and `compute_society_contact` / `compute_society_contact_metric`. Derive pair onset, `contact_event_count`, `contact_pair_count`, `contact_location_tick_count`, `cross_community_person_ticks`, interaction counts by closed dyadic kind, `cross_community_kinship_edge_count`, and coverage/availability. Report `ProjectContributed` / `PublicGoodMaintained` separately as collective participation counts only when the project or public good spans communities; unpaired collective acts are coverage, not cross-community cooperation. Use IDs/digests only; no group labels.
  - Acceptance: known-answer separated/co-located/arrival timelines; singleton/unassigned coverage; same-community interactions excluded from cross counts; collective acts without a counterparty are not counted as dyadic cooperation; absent channels stay absent; identical inputs produce identical ordering and fingerprints; family `society_contact@1`.
  - Logging: DEBUG per-pair counts and coverage; INFO family summary with pair count and availability; no content or region labels.
  - Dependencies: 3, 3a, v3-23 candidate communities.

- [x] **Task 7: Implement pre/post-contact cultural change.**
  - Files: create `src/analysis/contact_cultural_change.py`; update `src/analysis/__init__.py`; create `tests/unit/test_contact_cultural_change.py`.
  - Add `ContactDigestRow(dimension, person_id, token, tick)` and `compute_contact_cultural_change`. Use exact windows (`pre: tick < onset`, `post: onset <= tick <= final_tick`) per community pair and one **shared token universe per pair/dimension across both windows**. Accept an optional pre-onset candidate-community snapshot; compute JSD via `analysis.numerical.jensen_shannon_divergence`; report pre/post means, convergence delta, converging/continued-divergence pair counts, `membership_stability` (share of final members assigned to the same community in the pre-onset clustering), and coverage. Use notes code `descriptive_contact_association`.
  - Acceptance: identical distributions yield zero divergence; disjoint distributions yield the pinned JSD maximum; missing pre or post windows produce `partial`/`absent`, never zero; a token absent in one window is a real zero under the shared universe; membership change is exposed and does not silently become community-level convergence; when pre-onset communities are unavailable, membership stability is `partial`/`unknown` rather than assumed stable; both convergence and continued divergence are representable; no causal or success label; family `contact_cultural_change@1`.
  - Logging: DEBUG per-pair/dimension window counts and membership stability; INFO family summary; no tokens/digests of content in logs.
  - Dependencies: 6.

- [x] **Task 8: Implement hybrid-practice detection.**
  - Files: create `src/analysis/contact_hybrid_practice.py`; update `src/analysis/__init__.py`; create `tests/unit/test_contact_hybrid_practice.py`.
  - Consume detached practical-knowledge audit rows with parent entry IDs, cultural-feature recombined rows with parent/evidence lineage, narrative shared-root/merge rows, and naming/convention merge rows. Report hybrid counts, intercommunity combination count, shared-root pair count, merge count, `hybridization_rate = hybrid / post_contact_acquired_entries_with_resolvable_lineage` (denominator exposed), and unresolved lineage count. Resolve donor communities only from detached evidence; do not import ledgers.
  - Acceptance: same-community combination is not hybrid; cross-community parents count; unresolved parents stay unresolved; recombined cultural features with unknown donors are not counted as cross-community; no cultural-value judgment; family `contact_hybrid_practice@1`.
  - Logging: DEBUG lineage resolution counts; INFO family summary; no parent content or narrative text.
  - Dependencies: 6.

- [x] **Task 9: Implement knowledge and technology transfer.**
  - Files: create `src/analysis/contact_knowledge_transfer.py`; update `src/analysis/__init__.py`; create `tests/unit/test_contact_knowledge_transfer.py`.
  - Consume practical-knowledge audits and teaching audits. Resolve donor/recipient communities from owner/teacher/source IDs; report total transfers, per-channel counts (`teaching`, `imitation`, `written_record`, `reconstruction`, `combination`), donor→recipient pairs, mutated transfers, mean hop, fingerprint-distance/fidelity aggregates, and unresolved donors. Post-contact counts use contact onset.
  - Acceptance: same-community transfer is excluded from cross counts; unknown donor is unresolved, not zero; absent channels are absent; technology/knowledge content is represented only by digest/hop/provenance fields; family `contact_knowledge_transfer@1`.
  - Logging: DEBUG donor/recipient resolution counts; INFO family summary; no technique descriptions, fingerprints, or content.
  - Dependencies: 6.

- [x] **Task 10: Implement lexical borrowing.**
  - Files: create `src/analysis/contact_lexical_borrowing.py`; update `src/analysis/__init__.py`; create `tests/unit/test_contact_lexical_borrowing.py`.
  - Consume metadata-only naming evidence rows (`owner_id`, `label_token`, `referent_kind`, `actor_id`, `channel`, `first_tick`, `last_tick`, `evidence_tick`, `transmission`, `lineage_ref`). A borrowing is a communicated evidence item whose actor belongs to a different community. Define **new adoption** as `evidence_tick == binding.first_tick` with no prior same-label evidence; later communicated evidence is reinforcement. Report borrowed-label count, borrowing-event count, donor→recipient pairs, new-adoption versus reinforcement/merge/competition counts, mean strength, and unresolved actors.
  - Acceptance: same-community communication is not borrowing; observed-only evidence is not borrowing; unknown actor is unresolved; new adoption and reinforcement are distinguishable; labels remain owner-scoped and no shared lexicon is produced; family `contact_lexical_borrowing@1`.
  - Logging: DEBUG resolution counts; INFO family summary; never log label text or referent descriptions.
  - Dependencies: 6.

- [x] **Task 11: Implement reputation transfer.**
  - Files: create `src/analysis/contact_reputation_transfer.py`; update `src/analysis/__init__.py`; create `tests/unit/test_contact_reputation_transfer.py`.
  - Consume detached reputation evidence rows (`owner_id`, `target_id`, `source_id`, `dimension`, `channel`, `source_trust_band`, `tick`). Count only `communication` and `third_party_story` evidence whose source and owner belong to different communities and whose source is not the target; direct observation and remembered interaction are first-hand evidence, not transfer. Report transfer events, donor→recipient pairs, target count, per-dimension counts, channel counts, trust-band counts, unresolved sources, and non-transfer direct/remembered coverage. Do not aggregate group reputation or write a mean back.
  - Acceptance: same-community testimony is excluded; direct observation and remembered interaction are not counted as cross transfer; source == target is rejected from transfer counts; unresolved source is counted; no group reputation label; family `contact_reputation_transfer@1`.
  - Logging: DEBUG resolution counts; INFO family summary; no reputation values or target content.
  - Dependencies: 6.

### Phase 4 — Composition, collection, and catalog

- [x] **Task 12: Add detached contact harvests and provenance exports.**
  - Files: `src/experiments/composition.py`, `collectors.py`, `metric_collection.py`, `src/simulation/runner.py`, `src/agents/cognition/semantic_naming.py`, `src/agents/cognition/reputation.py`; create `tests/unit/test_contact_composition.py`; update `tests/unit/test_society_composition.py`.
  - **(a) Contact harvest rows:** add `contact_episode_rows_from_events`, `contact_presence_rows_from_regional_input`, `contact_interaction_rows_from_events` (communication, completed exchange, teaching, dyadic cooperation, conflict, kinship, and separate collective participation), `contact_digest_rows_from_snapshot` with ticks (`trace.created_tick` or row `tick`), `contact_onset_rows` shared by all six families, `contact_pre_communities_at_onset` (fold residence as of `onset - 1` and cluster with interaction/trust edges up to onset), `contact_kinship_rows_from_events`, practical-knowledge parent-lineage rows, cultural-feature parent/evidence lineage rows, and narrative shared-root/merge plus naming/convention merge rows.
  - **(b) Provenance exports and collection wiring:** add metadata-only `NamingBorrowingAudit`/ledger export and `export_reputation_ledgers` (or equivalent detached evidence) so lexical/reputation families work in ordinary runs, not only hand-built arms. Wire the contact inputs, the shared onset rows, and the previously unwired society inputs into `MetricCollectionService`/collectors under fail-closed optional blocks.
  - Acceptance: restored snapshots reproduce live rows; manifest clamping applies; no analysis module imports persistence or ledgers; contact-off runs produce absent inputs without error; all contact families receive the same onset rows and ticked digests; IDs/tokens only; existing society inputs remain backward-compatible.
  - Logging: DEBUG row counts per lane; INFO harvest completion; WARN empty channel with safe code; no content.
  - Dependencies: 6–11.

- [x] **Task 13: Register six contact metric families and assembly.**
  - Files: `src/analysis/specifications.py` (`METRIC_FAMILY_COUNT` 97 → 103, six `MetricFamilyId` members, six specs/builders, `_BUILDERS`), `metric_service.py` (inputs, optional-block map, assembly), `src/analysis/__init__.py`; update `tests/unit/test_metric_specifications.py`, `test_metric_service.py`, and **all 19 `tests/unit/*` files pinning `METRIC_FAMILY_COUNT == 97`** (`rg -l "METRIC_FAMILY_COUNT == 97" tests/unit`).
  - Register `society_contact@1`, `contact_cultural_change@1`, `contact_hybrid_practice@1`, `contact_knowledge_transfer@1`, `contact_lexical_borrowing@1`, `contact_reputation_transfer@1`. Compute/expose contact onset first, then pass the shared `contact_onset_rows` to the five dependent families; assembly order is contact exposure → cultural change → hybrid practice → knowledge transfer → lexical borrowing → reputation transfer. Assembly stays sorted, fail-closed, and availability-aware; missing contact inputs emit absent documents without exceptions.
  - Acceptance: catalog validation passes at 103; flags-off/baseline and contact-off runs emit absent/partial availability; fingerprints are stable for identical inputs; all dependent families use the same onset rows; all family-count pins updated; no non-catalog family is introduced.
  - Logging: INFO at assembly with family ID and availability only; WARN safe code on absent optional block; no metric payloads.
  - Dependencies: 6–12.

### Phase 5 — Experiment, presentation, documentation, gates

- [x] **Task 14: Build Experiment BA cultural contact and catalog entry.**
  - Files: create `src/experiments/cultural_contact_scenario.py`; update `src/experiments/catalog.py` (`OFF_GATE_MATRIX_EXPERIMENT_IDS`), `src/experiments/__init__.py`, `matrix_schema.py`; create `tests/unit/test_experiment_ba.py`.
  - Register `cultural_contact@1` off the V1 gate. Two or more region-separated populations on v45 with owned channels; arms `ba-channel-off`, `ba-isolated`, `ba-contact-trade`, `ba-contact-teaching`, `ba-contact-conflict-cooperation`, `ba-contact-kinship`. `ba-isolated` enables contact recording but schedules no cross-region journeys, so contact events stay zero while contact metrics remain available as absent/partial; `ba-contact-*` arms use real journeys, and the conflict/cooperation arm exercises the Task 3a successful cross-region flee path when the scenario includes an escape. Use diagnostic command fixtures for deterministic coverage and at least one cognition-driven arm through normal perception/cognition. Arbiter asserts exact structural evidence: contact events in contact arms, none in off/isolated; six families present with coverage; trade/teaching/conflict/cooperation counts match evidence; flee-origin contact is recorded when applicable; kinship is present or explicitly absent; no unexplained transmission without a journey. Never assert convergence, assimilation, war, or cooperation success.
  - Acceptance: fixed seed reproduces trajectories/results; contact-off matches v4 baseline; matrix round-trips; off-gate membership is pinned; no scripted society/attitude injection.
  - Logging: INFO experiment/arm/run IDs and result counts; DEBUG arm schema/evidence coverage and arbiter assertion counts; no seeds, message text, or config dumps.
  - Dependencies: 2, 3a, 5, 13.

- [x] **Task 15: Add the Research UI contact view.**
  - Files: create `clients/research-ui/src/views/ContactPanel.svelte`; update `src/observer/research_ui_state.py` (`contact` in `RESEARCH_UI_VIEWS`/`_RUN_SCOPED_VIEWS`, six families in `_ANALYTICAL_OVERLAYS`), `clients/research-ui/src/router.ts` / `App.svelte` / deeplink and epistemic tests, `clients/research-ui/src/views/ContactPanel.test.ts`.
  - Render contact exposure, convergence/continued divergence, hybrid practices, knowledge transfer, lexical borrowing, and reputation transfer from the generic metric endpoints under `research_inference` with `analytical_inference` chrome. No backend API change, no Godot/observer protocol change, no content payloads.
  - Acceptance: view lists the six families with availability/coverage; analytical results are never shown as agent-visible facts; router/deeplink/epistemic tests pass.
  - Logging: none new beyond existing read-path logging.
  - Dependencies: 13.

- [x] **Task 16: Documentation checkpoint.**
  - Files: `docs/experiments.md` (Experiment BA + reproduction), `docs/analysis-metrics.md` (six families, formulas, availability, descriptive-not-causal note, shared windows/membership stability, reputation transfer channel boundary), `docs/architecture.md` (neutral contact boundary, counts 43/73/103, replay-v22/codec v20, no marriage), `docs/configuration.md` (v45 exact `cultural_contact` keys and gates), `docs/observer.md` (`CONTACT_RECORDED`), `docs/research-ui.md` (Contact view), `docs/physical-simulation.md` (arrival and non-journey relocation contact ordering), `docs/social-communication.md` (story exchange, knowledge transfer, lexical borrowing, reputation transfer semantics), `docs/development.md` (verification commands), README index as needed.
  - Document that migration/trade/communication/teaching/conflict/cooperation are existing mechanisms, contact adds only neutral co-presence, intermarriage is unsupported, and convergence/divergence are descriptive outcomes. Document that direct/remembered reputation evidence is not transfer and that `ProjectContributed`/`PublicGoodMaintained` are collective coverage, not dyadic contact cooperation. Fix stale metric-count references while touching the page.
  - Acceptance: docs match implementation; links/anchors valid; BA reproduction example succeeds; no claim of causal assimilation or hard-coded cultural outcomes.
  - Logging: N/A.
  - Dependencies: 14, 15.

- [x] **Task 17: Reconcile gates and final verification.**
  - Files: any fallout across tests, type annotations, fixtures, and docs indexes; no suppression or relaxed lint/type config.
  - Run and reconcile: full pytest; `tests/architecture`; `lint-imports`; Ruff and format; mypy; the required six-file V1/V2 compatibility gate; contact-specific config/replay/perception/memory/analysis tests including `test_contact_relocations.py`; registered Godot suite with `CONTACT_RECORDED` known-type coverage; disposable PostgreSQL/pgvector integration if persistence paths are exercised.
  - Acceptance: all required gates green or explicitly documented; command count 43; semantic count 73; metric family count 103; runner-config-v45; replay-v22/codec v20 contact-active and v21/v19 contact-off; Alembic head 0017; `/v1` and `observer-protocol-v1` unchanged; no new capability flag.
  - Logging: N/A.
  - Dependencies: 16.

- [x] **Task 18: Finish schema and Godot documentation updates for cultural contact.**
  - Files: `docs/simulation-runner.md`, `docs/persistence.md`, `docs/godot-observer.md`.
  - Update the canonical runner and persistence reference pages for the v45 contract: accepted runner schemas and selector (v45 = v44 family root plus required `cultural_contact`; `multi_polity_migration` + `regions_migration` required), contact-active write pair `(EVENT_SCHEMA_REPLAY_V22, "v20")`, contact-off regional pair `(21, "v19")`, replayable `ContactRecorded`, and the default write remaining `runner-config-v4` when contact is absent. Replace stale claims such as V3 requiring only `runner-config-v23`/legacy decode through v22 in `docs/simulation-runner.md:96` and the runner-config table/write-pair priority ending at v25/replay-v10/codec v7 in `docs/persistence.md:78`.
  - Add `CONTACT_RECORDED` to the Godot observer documentation's recognized semantic-type/log-routing list (`docs/godot-observer.md:41`) and note that it is presentation-only with no write authority or new layout.
  - Acceptance: the three pages agree with `simulation.compatibility.COMPATIBILITY_MATRIX`, `SUPPORTED_RUNNER_SCHEMA_VERSIONS`, `ACCEPTED_EVENT_SCHEMA_VERSIONS`, and `ACCEPTED_PERSISTENCE_CODEC_VERSIONS`; no stale v23-only, v25-terminal, or replay-v8-terminal claims remain in the touched sections; `CONTACT_RECORDED` is documented as a recognized semantic type; links/anchors resolve.
  - Logging: N/A.
  - Dependencies: 16.

## Verification Notes

- Metric-count pins: run `rg -l "METRIC_FAMILY_COUNT == 97" tests/unit` before Task 13 and update every match to 103. `tests/unit/metric_fixtures.py` is dynamic and needs no count edit.
- Semantic-count pins: run `rg -l "SEMANTIC_EVENT_TYPES|== 72" tests/unit tests/architecture` and update relevant assertions to 73; keep historical slices intact.
- Runner-config pins: v45 is the v44 family root plus required `cultural_contact`; update every v44-only `regions_migration`/`public_goods`/`collective_projects` schema set and add `_v45_family_root_keys` before writing tests.
- Replay pins: contact-off stays `(21, "v19")`; contact-active is `(22, "v20")`. Update only tests that select the contact-active pair; keep v21/v19 regional tests. Contact is replayable only when `event_is_replayable(ContactRecorded)` is true.
- Godot pins: add `CONTACT_RECORDED` to `KNOWN_TYPES`, routing, and event-log labels; run the registered Godot protocol suite. Unknown-type fallback is not sufficient for a presented contact mechanism.
- Six-file compatibility gate (from v3-22/v3-23 precedent):
  `uv run --frozen --python 3.12.14 pytest tests/unit/test_v1_regression_gate.py tests/unit/test_v2_scientific_invariants.py tests/unit/test_v3_v2_replay_compat.py tests/unit/test_v3_population_flags_off_compat.py tests/unit/test_compatibility_matrix.py tests/unit/test_domain_contract_evolution_policy.py -q`
- Baseline count assertions are selectors, not requirements: re-read `METRIC_FAMILY_COUNT`, `SEMANTIC_EVENT_TYPES`, `EVENT_SCHEMA_REPLAY_V*`, and `RUNNER_SCHEMA_VERSION_V*` before implementation if other feature work lands first.
