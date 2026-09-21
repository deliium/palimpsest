# Social Communication and Information Transmission

This note distinguishes **objective delivery**, **declared testimony**, **owner-scoped derivation**, and **read-only analysis**.

## Objective delivery (world authority)

`WorldEngine` alone admits `Talk` / `Ask` / `Tell` and records `Talked` / `Asked` / `Told`. A successful communication event proves only that an utterance was delivered to a living, colocated, visibility-compatible recipient. It does **not** prove the content is true.

Eligibility is private world policy: living sender, distinct living recipient, compatible location/range, and perception/visibility at resolution time. Delivery is recipient-private and appears on the next observation window. The world does not auto-answer `Ask`, infer truth from `Tell`, or mutate relationships.

## Declared testimony (speaker-owned)

`StructuredUtterance` carries speaker-declared lineage: communication id, immediate source, optional parent communication correlation, ordered source-agent chain, hop count, sender confidence, and source basis. Receivers may distrust, ignore, or reinterpret that lineage. World-verified fields remain event id, actor, recipient, tick, and delivery outcome.

Retelling uses `retell_utterance`: append the new speaker and hop; never copy another agent's memory, reconstruction, belief, or relationship ids.

## Owner-scoped derivation (cognition / memory)

Each listener builds a **fresh** `MemoryTrace` with `CommunicatedTransmissionMeta`. Cognition never copies the sender's episodic state. Semantic belief updates treat communicated evidence as testimony: trust, confidence, hop attenuation, and context relevance may yield accept / discount / contradict / defer. Memory traces are retained even when belief revision is deferred. Generic communication may raise familiarity; trust changes only from explicit corroboration/contradiction signals.

## Read-only analysis

`SocialTransmissionAnalysisService` joins communication events with communicated traces after the fact. It reports hop counts, unique agents reached, fan-out, and per-hop structured additions/losses without feeding results back into live cognition. Logs and analysis `repr` expose IDs, counts, hops, and confidence bands — never message text, propositions, narratives, or fingerprints as payload surrogates.
