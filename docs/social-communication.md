# Social Communication and Information Transmission

This note distinguishes **objective delivery**, **declared testimony**, **owner-scoped derivation**, and **read-only analysis**.

## Objective delivery (world authority)

`WorldEngine` alone admits `Talk` / `Ask` / `Tell` and records `Talked` / `Asked` / `Told`. A successful communication event proves only that an utterance was delivered to a living, colocated, visibility-compatible recipient. It does **not** prove the content is true.

Eligibility is private world policy: living sender, distinct living recipient, compatible location/range, and perception/visibility at resolution time. Delivery is recipient-private and appears on the next observation window. The world does not auto-answer `Ask`, infer truth from `Tell`, or mutate relationships.

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

## Owner-scoped derivation (cognition / memory)

Each listener builds a **fresh** `MemoryTrace` with `CommunicatedTransmissionMeta`. Cognition never copies the sender's episodic state. Semantic belief updates treat communicated evidence as testimony: trust, confidence, hop attenuation, and context relevance may yield accept / discount / contradict / defer. Memory traces are retained even when belief revision is deferred. Generic communication may raise familiarity; trust changes only from explicit corroboration/contradiction signals.

## Read-only analysis

`SocialTransmissionAnalysisService` joins communication events with communicated traces after the fact. It reports hop counts, unique agents reached, fan-out, and per-hop structured additions/losses without feeding results back into live cognition. Logs and analysis `repr` expose IDs, counts, hops, and confidence bands — never message text, propositions, narratives, or fingerprints as payload surrogates.
