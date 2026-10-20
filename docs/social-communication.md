# Social Communication and Information Transmission

This note distinguishes **objective delivery**, **declared testimony**, **owner-scoped derivation**, and **read-only analysis**.

## Objective delivery (world authority)

`WorldEngine` alone admits `Talk` / `Ask` / `Tell` and records `Talked` / `Asked` / `Told`. A successful communication event proves only that an utterance was delivered to a living, colocated, visibility-compatible recipient. It does **not** prove the content is true.

Eligibility is private world policy: living sender, distinct living recipient, compatible location/range, and perception/visibility at resolution time. Delivery is recipient-private and appears on the next observation window. The world does not auto-answer `Ask`, infer truth from `Tell`, or mutate relationships.

`DeclareCommitment` is a separate public speech act. Free-text `Talk` is not parsed into a promise, exchange, debt, service, or condition. The event records closed tokens. It does not move an item, change health, reject a later command, or create a world-owned agreement. A `Give` in the same tick is a separate command. Identity `COMMITMENT` stays a self-belief about the owner's own goal. Relationship `DEBT` stays a scalar. Neither is this speech act.

`NegotiateExchange` is a separate command. It is available only when `subjective_valuation` is present on `runner-config-v40`. `offer`, `counteroffer`, and `withdraw` write negotiation history and move nothing. `accept` moves the item ids both sides named, together, or it moves none. `Talk` is not parsed into an offer. A `Give` in the same tick stays a one-item transfer and does not cancel a live offer. A commitment remembers a debt and does not collect it. The world row `exchange_offers` stores the parties, the item ids, and the tick. It stores no reservation integer. A reservation stays on the owner's private ledger. A completed event lists the items that moved. It does not publish a market price.

`TeachingInteractionMode` defaults to `DISABLED`. When both the speaker and the recipient are in the run's teaching set, a delivered `Talk`, `Ask`, or `Tell` may carry exactly one closed relation: `request_instruction`, `explain`, `demonstrate`, or `practice_together`. An `explain` object is `{domain}:{band}` with band `low`, `uncertain`, or `high`. The band is the speaker's own quantized believed level: below `0.34` is `low`, below `0.67` is `uncertain`, and `0.67` and above is `high`. Belief uptake uses the owner's trust toward the speaker. A missing profile uses `0.5`. The recipient does not receive the speaker's hidden objective level, support mass, or relationship profile.

## Declared testimony (speaker-owned)

`StructuredUtterance` carries speaker-declared lineage: communication id, immediate source, optional parent communication correlation, ordered source-agent chain, hop count, sender confidence, and source basis. Receivers may distrust, ignore, or reinterpret that lineage. World-verified fields remain event id, actor, recipient, tick, and delivery outcome.

Retelling uses `retell_utterance`: append the new speaker and hop; never copy another agent's memory, reconstruction, belief, or relationship ids. A retell whose hop count is greater than 1 stays dropped. `multi_hop_testimony_tracking` is still unowned.

## Private reputation

`ReputationMode` defaults to `DISABLED` and is not a capability flag. Off leaves the owner's ledger unset and does not change commands. `DETERMINISTIC` keeps a private `(owner, target)` ledger with four independent signed dimensions: `reliability`, `harm`, `generosity`, and `competence`. Words such as trustworthy or dangerous are analysis readings only.

Evidence uses four channels:

| Channel | Source |
| --- | --- |
| `direct_observation` | This tick's `help`, `give`, or successful `attack` by a resolved actor |
| `remembered_interaction` | An older trace of the owner's own participation, at half scale |
| `communication` | A hop-0 or hop-1 utterance whose subject resolves to the speaker |
| `third_party_story` | A hop-0 or hop-1 utterance whose subject resolves to some other agent |

Hop count above 1 adds nothing. Spoken adoption moves the listener toward the testified value by `0.5 * source_trust`. Missing relationship trust uses the existing neutral pair and records `source_trust_missing`. Direct observation and remembered interaction ignore that float. A self-report about the listener does not update a ledger.

## Per-utterance strategy

`CommunicationStrategyMode` defaults to `DISABLED` and is not a capability flag. Disabled selection returns today's command and no intent. `DETERMINISTIC` may render one claim as truthful, uncertain, a `decline` refusal, an omission, a selective disclosure, an exaggeration, or one substituted token the speaker already holds.

The choice is a `CommunicationIntent`. The world receives only the `Talk`, `Ask`, or `Tell`. An omission keeps the intent with `delivered=False` and the planner emits `Wait`. The utterance does not carry strategy, stance, or an analysis category.

`communication_strategy@1` assigns the labels after the run. `memory_error` is only an `assert_match` whose `cited_event_id` names a committed occurrence that does not cover the source tokens. `uncertain_inference` and `deliberate_deception` are the other two failure labels. Refusal and omission are `not_asserted`. The listener's observation, memory trace, and trust update do not receive those labels. An uncontradicted false statement does not itself change trust; a later contradiction still uses the existing testimony path.

## Subjective territorial claims

A claim is an owner-scoped belief about a location, a shelter, a stored resource, or a place that owner has used often. It is not a field on the world. `WorldEngine` still admits a `Take`, `Move`, `Harvest`, `Eat`, `Drink`, or `Store` that the physical rules allow. The observer frame stays the objective scene (`observer-protocol-v1`) and rejects a claim, contest, or controller key. One selected owner's heads are a separate subjective-claims query. `spatial_control@1` is a later reading of the committed log, marked research analytics, and is not an input to cognition. `TerritorialClaimMode` defaults to `DISABLED`. `runner-config-v15` is emitted only when that mode is `DETERMINISTIC`. The policy version is `territorial-claims.v1`. Claim strengths and utterance bodies are not written at INFO.

## Emergent groups

A candidate cluster, a membership belief, and a `GroupConcept` are different records. Analysis may find a cluster after the run. An agent may hold a private stance of `we`, `our_group`, or `those_agents` toward a set of agents. A `GroupConcept` is minted only when that belief has social evidence, witnessed assistance, exchange, or communication, and support of at least `0.40`. Proximity, trust, and shared harm raise support without minting a concept. One owner may hold overlapping concepts. Support decays. Two owners may disagree. A concept may split or merge inside one ledger. None of those records is a team on the world, and `emergent_group_formation@1` is not an input to cognition. `group_community_structure` stays the trust-only modularity family. The policy version is `group-formation.v1`.

## Emergent social norms

Repeated behavior, an owner's norm belief, and that owner's response are different objects. Analysis may count give, sleep, and attack regularities after the run. `repeated_conventions@1` stays the motif family and is not rewritten. An owner may keep a private expectation that becomes active only after repeated conforming evidence. A response is `follow`, `ignore`, `violate`, `communicate`, or `enforce`, and it only prefers futures the planner already has. Sanctions are an existing talk, help, give, or attack, or a private trust revision, chosen by the owner. They do not reject a command inside `WorldEngine`. `SocialNormMode` defaults to `DISABLED`. `runner-config-v17` is emitted only when that mode is `DETERMINISTIC`. Experiment X and `emergent_social_norms@1` stay off the V1 gate and out of cognition. The policy version is `social-norms.v1`.

## Repeated social conventions

Objective repetition, an owner's habit belief, and analytical ritual/tradition labels are different objects. Analysis may count meetings, timed gatherings, exchanges, and collective actions after the run via `persistent_social_conventions@1`. `repeated_conventions@1` stays the motif family and is not rewritten. An owner may keep a private habit of the form "we usually do X in situation Y," learned from observation, reinforced by already-loaded memories, and adopted from closed `usually` / `custom` utterances. Habits track participants, duration, transmission, remembered explanations, and competing variants. Habit bias only prefers futures the planner already has. Ritual and tradition labels stay analysis-only until an agent itself reaches conceptualization `named_custom`. They are never world fields or tradition scripts. `SocialConventionMode` defaults to `DISABLED`. `runner-config-v18` is emitted only when that mode is `DETERMINISTIC`. Experiment Y and `persistent_social_conventions@1` stay off the V1 gate and out of cognition. The policy version is `social-conventions.v1`.

## Emergent semantic naming

Objective identity and an owner's private label are different layers. Agents mint closed snake_case label tokens from owner-scoped digests — never from `ObservedLocation.name`, exit names, or other free-text world names. Each `LabelBinding` may hold private candidate referents; other agents never receive those candidate rows. Social spread uses delivered `call` utterances as closed tokens only, without auto-grounding speaker mappings for non-listeners. `NamingCueSummary` carries duck-typed group/practice tokens from already-updated snapshot fields and keeps naming import-closed from sibling ledgers. Labels may spread, compete, merge, shift meaning, and disappear under locked thresholds. Analysis-only `emergent_semantic_naming@1` reports vocabulary convergence and semantic drift after the run; it is not an input to cognition. `SemanticNamingMode` defaults to `DISABLED`. `runner-config-v20` is emitted only when that mode is `DETERMINISTIC`. Experiment AA stays off the V1 gate. The policy version is `semantic-naming.v1`.

## Long-lived cultural narratives

V1 rumor provenance extends into owner-scoped narrative lineages. An owner may track recurring story variants from observation, memory reinforcement, reconstruction cues, deliberate unreferenced lies, distorted-artifact cues, and feature-local `tell_story` / `retell` / `merge_story` utterances. `NarrativeCueSummary` carries duck-typed distorted-artifact and reconstruction tokens without importing sibling ledgers. Lineages may branch, merge, decay, and optionally uplift into existing semantic beliefs only via gated `BeliefRevisionRequest` intents. Hard-coded Myth objects and automatic society-wide narrative influence are forbidden. Analysis-only `cultural_narrative_lineage@1` reports persistence, mutation, distortion, source loss, convergence, and geographic/social spread after the run; it is not an input to cognition. `CulturalNarrativeMode` defaults to `DISABLED`. `runner-config-v21` is emitted only when that mode is `DETERMINISTIC`. Experiment AB stays off the V1 gate. The policy version is `cultural-narratives.v1`.

## Owner-scoped derivation (cognition / memory)

Each listener builds a **fresh** `MemoryTrace` with `CommunicatedTransmissionMeta`. Cognition never copies the sender's episodic state. Semantic belief updates treat communicated evidence as testimony: trust, confidence, hop attenuation, and context relevance may yield accept / discount / contradict / defer. Memory traces are retained even when belief revision is deferred. Generic communication may raise familiarity; trust changes only from explicit corroboration/contradiction signals.

## Read-only analysis

`SocialTransmissionAnalysisService` joins communication events with communicated traces after the fact. It reports hop counts, unique agents reached, fan-out, and per-hop structured additions/losses without feeding results back into live cognition. Logs and analysis `repr` expose IDs, counts, hops, and confidence bands — never message text, propositions, narratives, or fingerprints as payload surrogates.


## Contact transfer semantics

Trade, communication, teaching, conflict, and cooperation remain the existing
objective events; the contact layer only conditions their counts on candidate
communities. Story exchange is represented by shared narrative transmission roots
and cross-community narrative merges (no narrative text enters metrics or logs).
Lexical borrowing requires communicated evidence whose actor belongs to another
community; labels remain owner-scoped. Reputation transfer counts only
`communication` and `third_party_story` evidence from a different community and
never aggregates a group reputation or writes a mean back to an owner.

## Bounded compositional symbols

`SymbolicLanguageMode` is an optional per-agent treatment over the existing
private terminology ledger. A composition combines exactly two already-active
label tokens with one closed operator: `attributive` (head plus modifier) or
`relational` (subject plus relatum). Parts must be label tokens, never nested
composition ids. At most two compositions ride on one existing `Talk`; the
message carries one `call` atom per constituent and one operator atom per
composition. `communication.v1`, command kinds, and event kinds are unchanged.

Composition meaning stays owner-scoped. A speaker sends tokens and an operator
only — never its referent hypothesis or confidence. A listener learns only when
both constituents resolve to its own active bindings; otherwise it records
`partial`/`unresolved` and mints nothing. Two owners using the same surface form
therefore hold two different composition ids. Different populations may diverge,
and contact borrowing requires ordinary delivered communication. There is no
global lexicon, no grammar induction, no free-form text, and no convergence
success condition. Analysis is detached and digest-only. The policy version is
`symbolic-language.v1`.

## Sense history and semantic drift

A label binding or symbolic composition may retain a bounded history of at most
16 sense records. Records are appended only when the locked policy promotes a
sense, records a meaning shift, or absorbs associations through an exact merge.
Each record carries the logical tick, ordinal, closed trigger, referent kind,
opaque referent id, associated ids, and quantized confidence. Ordinary
observation, memory reinforcement, and decay add no sense record. Disabled modes
create no history.

History remains owner-scoped. A term may keep one meaning for the whole run,
shift once, or differ between populations; all outcomes are valid. Contact can
change a meaning only through existing delivered communication. There is no
shared dictionary, no world authority for meaning, and no convergence success
condition. Detached analysis may compare 16-character surface digests and
referent digests across owners, but owner-scoped ids are never treated as shared
identity, and analysis never re-enters cognition. The policy versions remain
`semantic-naming.v1` and `symbolic-language.v1`, and the 16-record cap is not
configurable.


## Cross-cultural translation

Translation is an owner-scoped hypothesis, not a dictionary. A listener may
infer that a foreign surface term corresponds to one or more of its own active
`LabelBinding` values from shared observation, demonstration, repeated
interaction, teaching, observed artifacts, or context. Every mapping records
bounded targets, confidence, provenance, and an owner structural fit
(`resolved`, `partial`, `ambiguous`, `unresolved`). `exact`, `partial`,
`ambiguous`, and `wrong` exist only in detached analysis; the engine never
corrects a mapping and never lets one owner read another owner's mapping.

Active unambiguous mappings may add a bounded translated copy of a delivered
relation to the listener's own communicated memory, substitute foreign
composition parts during symbolic interpretation, and rewrite at most two own
`call` terms in an ordinary `Talk`/`Ask`/`Tell` toward the recipient who taught
the foreign term. These paths are ordinary owner-scoped testimony and social
action; a wrong mapping can therefore support a wrong belief or a
misunderstanding without any engine correction. Disabled translation allocates
no ledger and leaves traces byte-identical.

## Collective-decision relation recipe

Collective-decision acts use a namespaced closed recipe over the existing
`CommunicationRelation` atoms: `collective_propose`, `collective_support`,
`collective_oppose`, `collective_delegate`, `collective_withdraw`, and
`collective_coordinate`, plus a `collective_policy` marker naming
`collective-decisions.v1`. The topic is the relation subject; the proposal
reference, revision, and act payload are bounded tokens in the object. The
verified observed speaker is the actor. Payload actors and declared roots are
never authentication, and a relay is testimony rather than direct support.
Ordinary conversation is unaffected, and no broadcast is introduced.
